"""
Utilitário de Gerenciamento de Processos Windows via Win32 Job Object.
Garante que subprocessos (FastAPI, Ollama, etc.) sejam atrelados ao kernel do Windows
com a flag JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000).

Se o processo pai sofrer um crash fatal, for terminado via Gerenciador de Tarefas
ou o handle do Job Object for fechado, o kernel do Windows extermina instantaneamente
toda a árvore de processos filhos, impedindo processos zumbis na RAM.
"""

import os
import sys
import ctypes

_global_job_handle = None


def setup_job_object_kill_on_close():
    """
    Cria e configura um Windows Job Object com JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000)
    e vincula o processo atual. Retorna o handle do Job Object ou None em caso de falha/não-Windows.
    """
    global _global_job_handle
    if sys.platform != 'win32':
        return None

    if _global_job_handle is not None:
        return _global_job_handle

    try:
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32

        JOBOBJECT_EXTENDED_LIMIT_INFORMATION = 9
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ('ReadOperationCount', ctypes.c_uint64),
                ('WriteOperationCount', ctypes.c_uint64),
                ('OtherOperationCount', ctypes.c_uint64),
                ('ReadTransferCount', ctypes.c_uint64),
                ('WriteTransferCount', ctypes.c_uint64),
                ('OtherTransferCount', ctypes.c_uint64),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('PerProcessUserTimeLimit', ctypes.c_int64),
                ('PerJobUserTimeLimit', ctypes.c_int64),
                ('LimitFlags', wintypes.DWORD),
                ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', wintypes.DWORD),
                ('Affinity', ctypes.c_size_t),
                ('PriorityClass', wintypes.DWORD),
                ('SchedulingClass', wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION_STRUCT(ctypes.Structure):
            _fields_ = [
                ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ('IoInfo', IO_COUNTERS),
                ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryLimit', ctypes.c_size_t),
                ('PeakJobMemoryLimit', ctypes.c_size_t),
            ]

        hJob = kernel32.CreateJobObjectW(None, None)
        if not hJob:
            return None

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION_STRUCT()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        success = kernel32.SetInformationJobObject(
            hJob,
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info)
        )
        if not success:
            err = kernel32.GetLastError()
            kernel32.CloseHandle(hJob)
            print(f"[Win32 Job] SetInformationJobObject falhou com erro: {err}")
            return None

        # Atribui o processo atual ao Job usando handle real com PROCESS_SET_QUOTA e PROCESS_TERMINATE
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        hCurProc = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, os.getpid())
        if hCurProc:
            try:
                kernel32.AssignProcessToJobObject(hJob, hCurProc)
            finally:
                kernel32.CloseHandle(hCurProc)

        _global_job_handle = hJob
        return _global_job_handle
    except Exception as e:
        print(f"[Win32 Job] Aviso ao inicializar Job Object: {e}")
        return None


def assign_pid_to_job(pid: int) -> bool:
    """
    Atribui um processo externo/filho (ex: ollama.exe) pelo PID ao Job Object global.
    """
    if sys.platform != 'win32' or not pid or pid <= 0:
        return False

    job_handle = setup_job_object_kill_on_close()
    if not job_handle:
        return False

    try:
        kernel32 = ctypes.windll.kernel32
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        hProcess = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, int(pid))
        if not hProcess:
            return False

        try:
            res = kernel32.AssignProcessToJobObject(job_handle, hProcess)
            return bool(res)
        finally:
            kernel32.CloseHandle(hProcess)
    except Exception:
        return False
