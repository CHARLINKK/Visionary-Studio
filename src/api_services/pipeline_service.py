import os
import sys
import json
import re
import datetime
import threading
import time
from src.config import Config

class PipelineService:
    """
    Serviço central de execução do pipeline (OCR, Layout, Tradução) em background.
    Gerencia o ciclo de vida dos jobs em threads dedicadas e previne condições de corrida utilizando locks.
    
    Orquestração:
    - O `_pipeline_lock` (Global RLock) garante que apenas um job de pipeline execute as inferências 
      na GPU por vez, evitando esgotamento de VRAM.
    - O `_jobs_lock` protege a lista de tarefas ativas contra acessos assíncronos das chamadas RPC do React.
    """

    MAX_RETAINED_JOBS = 50

    @staticmethod
    def _resolve_settings_and_bridge(settings_service=None, api_bridge=None):
        if hasattr(settings_service, "getSettings"):
            return settings_service, api_bridge
        if hasattr(api_bridge, "getSettings"):
            return api_bridge, api_bridge
        if hasattr(settings_service, "_settings_service"):
            return getattr(settings_service, "_settings_service", None), settings_service
        if hasattr(api_bridge, "_settings_service"):
            return getattr(api_bridge, "_settings_service", None), api_bridge
        return None, settings_service or api_bridge

    def __init__(self, settings_service=None, api_bridge=None, max_retained_jobs=50):
        self.settings_service, self.api = self._resolve_settings_and_bridge(
            settings_service, api_bridge
        )
        self.max_retained_jobs = max_retained_jobs
        self._active_jobs = {}
        self._job_sessions = {}
        self._jobs_lock = threading.Lock()
        self._current_running_job_id = None
        self._job_queue = []
        self._pending_tasks = []
        self._worker_thread = None

    def _evict_old_terminal_jobs(self):
        """
        Limita o histórico retido em memória de jobs finalizados (completed, failed, cancelled)
        para evitar consumo desnecessário de RAM em sessões longas.
        Jobs ativos (running, queued, pending) nunca são descartados.
        Deve ser invocado segurando self._jobs_lock.
        """
        terminal_jobs = [
            (jid, jinfo.get("finished_at", jinfo.get("created_at", 0)))
            for jid, jinfo in self._active_jobs.items()
            if jinfo.get("status") in ("completed", "failed", "cancelled")
        ]
        excess = len(terminal_jobs) - self.max_retained_jobs
        if excess > 0:
            terminal_jobs.sort(key=lambda x: x[1])
            for jid, _ in terminal_jobs[:excess]:
                self._active_jobs.pop(jid, None)
                self._job_sessions.pop(jid, None)

    def _broadcast_job_status(self, job_id, updates):
        try:
            from src.server import broadcast_log_sync
            broadcast_log_sync("job_status", "", extra={"job_id": job_id, "updates": updates})
        except Exception:
            pass

    def getJobStatus(self, job_id):
        with self._jobs_lock:
            job = self._active_jobs.get(job_id)
            if job:
                return {
                    "success": True,
                    "job_id": job_id,
                    "status": job.get("status", "running"),
                    "progress": job.get("progress", 0),
                    "step_label": job.get("step_label", ""),
                    "logs": list(job.get("logs", [])),
                    "error": job.get("error", None)
                }
            return {"success": False, "error": "Job not found"}

    def getPipelineStatus(self):
        with self._jobs_lock:
            return {
                "success": True,
                "jobs": {jid: dict(jinfo) for jid, jinfo in self._active_jobs.items()}
            }

    def clearCompletedJobs(self):
        with self._jobs_lock:
            to_remove = [jid for jid, jinfo in self._active_jobs.items() if jinfo.get("status") in ("completed", "failed", "cancelled")]
            for jid in to_remove:
                del self._active_jobs[jid]
            return {"success": True, "cleared_count": len(to_remove)}

    def clearJobLogs(self, job_id):
        with self._jobs_lock:
            if job_id in self._active_jobs:
                self._active_jobs[job_id]["logs"] = []
                return {"success": True}
            return {"success": False, "error": "Job not found"}

    def _execute_single_job(self, job_id, data, folder_path, folder_name):
        from src.run_batch import run_batch_pipeline, _pipeline_lock
        from src.batch_pipeline.session import BatchPipelineSession, scoped_session
        service_self = self
        job_session = BatchPipelineSession()
        with service_self._jobs_lock:
            # Verifica se o job foi cancelado na fila antes de disputar o lock do pipeline
            jinfo = service_self._active_jobs.get(job_id)
            if not jinfo or jinfo.get("status") == "cancelled":
                if job_id in service_self._job_queue:
                    service_self._job_queue.remove(job_id)
                return
            service_self._job_sessions[job_id] = job_session

        try:
            steps = data.get('steps', {})
            has_layout = steps.get('layout', True)
            has_ocr = steps.get('ocr', True)
            has_translate = steps.get('translate', True)

            skip_ocr = not has_layout and not has_ocr
            skip_trans = not has_translate
            only_layout = has_layout and not has_ocr
            resume_from_layout = not has_layout and has_ocr

            from src.utils.logger import get_logger
            pipeline_logger = get_logger("pipeline")
            pipeline_logger.info(f"Start Batch -> data: {data} | skip_ocr: {skip_ocr} | skip_trans: {skip_trans}")
            pipeline_logger.info(f"files_list: {data.get('files')}")

            from src.utils.pipeline_emitter import PipelineEmitter, scoped_job_stdout
            emitter = PipelineEmitter(job_id, service=service_self)

            was_canceled = False
            was_failed = False
            with scoped_session(job_session):
                with _pipeline_lock:
                    # Verifica se o job foi cancelado na fila enquanto aguardava a liberação da GPU
                    with service_self._jobs_lock:
                        jinfo = service_self._active_jobs.get(job_id)
                        if not jinfo or jinfo.get("status") == "cancelled":
                            if job_id in service_self._job_queue:
                                service_self._job_queue.remove(job_id)
                            return
                        service_self._current_running_job_id = job_id
                        service_self._active_jobs[job_id]["status"] = "running"
                        service_self._active_jobs[job_id]["step_label"] = "Iniciando pipeline..."

                    service_self._broadcast_job_status(job_id, {
                        "status": "running",
                        "currentStepLabel": "Iniciando pipeline..."
                    })

                    _vram_stop = threading.Event()

                    def _vram_loop():
                        try:
                            from src.utils.vram_monitor import get_vram_snapshot
                        except Exception:
                            return
                        while not _vram_stop.wait(2.0):
                            try:
                                snap = get_vram_snapshot()
                                emitter.emit_vram_realtime(snap)
                            except Exception:
                                pass

                    _vram_thread = threading.Thread(target=_vram_loop, daemon=True)
                    _vram_thread.start()

                    try:
                        with scoped_job_stdout(emitter):
                            if self.settings_service and hasattr(self.settings_service, "getSettings"):
                                settings = self.settings_service.getSettings()
                            elif self.api and hasattr(self.api, "getSettings"):
                                settings = self.api.getSettings()
                            else:
                                settings = Config.load()
                            pipe_success = run_batch_pipeline(
                                input_dir=folder_path,
                                output_dir=os.path.join(folder_path, "output"),
                                preset=data.get('tone', 'neutral'),
                                model=data.get('model') or settings.get('translation_model') or (settings.get('selected_models') or {}).get('transPol') or ("amadeus:7b" if not getattr(Config, "is_high_vram", lambda: False)() else "amadeus:14b"),
                                skip_ocr=skip_ocr,
                                debug=settings.get('debugPanelMaps', False),
                                skip_translate=skip_trans,
                                only_layout=only_layout,
                                resume_from_layout=resume_from_layout,
                                overwrite=data.get('overwrite', False),
                                files_list=data.get('files'),
                                deep_validation=data.get('deepValidation', False),
                                progress_emitter=emitter,
                                session=job_session,
                                direction=str(data.get('readingDirection') or data.get('direction') or 'rtl').strip().lower(),
                            )
                            if job_session.cancel_event.is_set():
                                was_canceled = True
                            elif pipe_success is False:
                                was_failed = True
                    finally:
                        _vram_stop.set()
                        _vram_thread.join(timeout=3.0)
                        with service_self._jobs_lock:
                            if service_self._current_running_job_id == job_id:
                                service_self._current_running_job_id = None
                            if job_id in service_self._job_queue:
                                service_self._job_queue.remove(job_id)

            if was_canceled:
                with service_self._jobs_lock:
                    if job_id in service_self._active_jobs:
                        service_self._active_jobs[job_id]["status"] = "cancelled"
                        service_self._active_jobs[job_id]["step_label"] = "Cancelado pelo usuário"
                        service_self._active_jobs[job_id]["finished_at"] = time.time()
                        service_self._evict_old_terminal_jobs()

                service_self._broadcast_job_status(job_id, {
                    "status": "cancelled",
                    "currentStepLabel": "Cancelado pelo usuário"
                })
                return

            if was_failed:
                err_msg = "Falha no pipeline: Verifique os modelos selecionados e os arquivos de entrada."
                with service_self._jobs_lock:
                    if job_id in service_self._active_jobs:
                        service_self._active_jobs[job_id]["status"] = "failed"
                        service_self._active_jobs[job_id]["error"] = err_msg
                        service_self._active_jobs[job_id]["step_label"] = "Falha na execução"
                        service_self._active_jobs[job_id]["finished_at"] = time.time()
                        service_self._evict_old_terminal_jobs()

                service_self._broadcast_job_status(job_id, {
                    "status": "failed",
                    "error": err_msg,
                    "currentStepLabel": "Falha na execução"
                })
                return

            if not skip_trans:
                self.finalizePipeline({"inputPath": folder_path, "finalName": folder_name})

            with service_self._jobs_lock:
                if job_id in service_self._active_jobs:
                    service_self._active_jobs[job_id]["status"] = "completed"
                    service_self._active_jobs[job_id]["progress"] = 100
                    service_self._active_jobs[job_id]["step_label"] = "Concluído"
                    service_self._active_jobs[job_id]["finished_at"] = time.time()
                    service_self._evict_old_terminal_jobs()

            service_self._broadcast_job_status(job_id, {
                "status": "completed",
                "progress": 100,
                "currentStepLabel": "Concluído"
            })

        except Exception as e:
            import traceback

            _is_oom = ("CUDA out of memory" in str(e) or "OutOfMemoryError" in type(e).__name__)
            if not _is_oom:
                try:
                    import torch
                    _is_oom = isinstance(e, torch.cuda.OutOfMemoryError)
                except Exception:
                    pass

            if _is_oom:
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
                _err_display = (
                    "⚠️ CUDA Out of Memory! A VRAM da GPU ficou sem espaço durante o processamento. "
                    "Feche outros programas que usam GPU, aguarde alguns segundos e tente novamente. "
                    "Se o erro persistir, reduza o número de imagens no lote."
                )
            else:
                _err_display = str(e)

            tb_str = traceback.format_exc()
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            log_line = f"[{now_str}] [ERROR] {_err_display}\n{tb_str}"

            with service_self._jobs_lock:
                if job_id in service_self._active_jobs:
                    service_self._active_jobs[job_id]["status"] = "failed"
                    service_self._active_jobs[job_id]["error"] = _err_display
                    service_self._active_jobs[job_id]["logs"].append(log_line)
                    service_self._active_jobs[job_id]["finished_at"] = time.time()
                    service_self._evict_old_terminal_jobs()

            try:
                from src.server import broadcast_log_sync
                broadcast_log_sync("job_log", "", extra={"job_id": job_id, "logs": [log_line]})
            except Exception:
                pass

            service_self._broadcast_job_status(job_id, {
                "status": "failed",
                "error": _err_display,
                "currentStepLabel": "Erro: " + (_err_display[:80] + "..." if len(_err_display) > 80 else _err_display)
            })
        finally:
            with service_self._jobs_lock:
                service_self._job_sessions.pop(job_id, None)

    def _worker_loop(self):
        while True:
            with self._jobs_lock:
                if not self._pending_tasks:
                    self._worker_thread = None
                    return
                job_id, data, folder_path, folder_name = self._pending_tasks.pop(0)
            self._execute_single_job(job_id, data, folder_path, folder_name)

    def queueJob(self, data):
        try:
            if not isinstance(data, dict):
                return {"success": False, "error": "Payload inválido: esperado um dicionário"}

            folder_path = data.get('folderPath', '')
            if not folder_path or not str(folder_path).strip():
                return {"success": False, "error": "Caminho do diretório ('folderPath') não especificado."}

            import uuid
            job_id = data.get('job_id') or str(uuid.uuid4())
            folder_name = os.path.basename(os.path.normpath(folder_path))

            start_worker = False
            with self._jobs_lock:
                self._evict_old_terminal_jobs()
                if len(self._pending_tasks) >= 100:
                    return {
                        "success": False,
                        "error": "Fila de tarefas cheia (limite de 100 tarefas atingido). Aguarde as tarefas em execução concluírem."
                    }
                is_busy = (self._current_running_job_id is not None) or bool(self._pending_tasks)
                self._job_queue.append(job_id)
                self._active_jobs[job_id] = {
                    "logs": [],
                    "progress": 0,
                    "status": "queued" if is_busy else "running",
                    "step_label": "Na fila..." if is_busy else "Iniciando...",
                    "error": None,
                    "vramRealtime": None,
                    "vramState": None,
                    "created_at": time.time()
                }
                self._pending_tasks.append((job_id, data, folder_path, folder_name))
                if self._worker_thread is None or not self._worker_thread.is_alive():
                    self._worker_thread = threading.Thread(
                        target=self._worker_loop,
                        daemon=True,
                        name="PipelineQueueWorker",
                    )
                    start_worker = True

            if is_busy:
                self._broadcast_job_status(job_id, {
                    "status": "queued",
                    "currentStepLabel": "Na fila...",
                    "progress": 0
                })

            if start_worker:
                self._worker_thread.start()

            return {"success": True, "job_id": job_id}
        except Exception as e:
            return {"success": False, "error": str(e)}


    def cancelJob(self, job_id, hard_reset=False):
        try:
            if str(job_id).lower() == "all":
                return self.cancelAllJobs(hard_reset=hard_reset)

            should_cancel_pipeline = False
            with self._jobs_lock:
                if job_id not in self._active_jobs:
                    self._active_jobs[job_id] = {}

                self._active_jobs[job_id]["status"] = "cancelled"
                self._active_jobs[job_id]["step_label"] = "Cancelado pelo usuário"
                self._active_jobs[job_id]["finished_at"] = time.time()
                self._evict_old_terminal_jobs()

                if self._current_running_job_id == job_id:
                    # Job está rodando na GPU
                    should_cancel_pipeline = True
                elif self._current_running_job_id is None:
                    # Nenhum job está registrado na GPU ainda
                    if not self._job_queue or self._job_queue[0] == job_id:
                        # Este job é o primeiro/único da fila ou chamada avulsa (ex: teste unitário)
                        should_cancel_pipeline = True
                    else:
                        # Há outro job antes deste na fila: não cancela a GPU
                        should_cancel_pipeline = False
                else:
                    # Outro job está rodando na GPU: não cancela a GPU
                    should_cancel_pipeline = False

                if job_id in self._job_queue:
                    self._job_queue.remove(job_id)
                self._pending_tasks = [t for t in self._pending_tasks if t[0] != job_id]

            # Feedback visual instantâneo para UI (zero latência)
            self._broadcast_job_status(job_id, {
                "status": "cancelled",
                "currentStepLabel": "Cancelado pelo usuário",
                "error": "Interrompido manualmente."
            })

            if should_cancel_pipeline:
                from src.run_batch import request_cancel
                print(f"[API] Cancelando execução do pipeline para job {job_id} (Hard Reset: {hard_reset})", flush=True)
                target_sess = None
                with self._jobs_lock:
                    target_sess = self._job_sessions.get(job_id)
                request_cancel(rollback=hard_reset, session=target_sess)
            else:
                print(f"[API] Job {job_id} estava na fila de espera. Cancelado antes de rodar sem afetar o job ativo.", flush=True)

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cancelAllJobs(self, hard_reset=False):
        try:
            cancelled_ids = []
            with self._jobs_lock:
                now_ts = time.time()
                for jid, jinfo in self._active_jobs.items():
                    if jinfo.get("status") in ("running", "pending", "queued"):
                        jinfo["status"] = "cancelled"
                        jinfo["step_label"] = "Cancelado pelo usuário"
                        jinfo["finished_at"] = now_ts
                        cancelled_ids.append(jid)
                self._job_queue.clear()
                self._pending_tasks.clear()
                self._evict_old_terminal_jobs()

            for jid in cancelled_ids:
                self._broadcast_job_status(jid, {
                    "status": "cancelled",
                    "currentStepLabel": "Cancelado pelo usuário",
                    "error": "Interrompido manualmente via menu/bandeja."
                })

            from src.run_batch import request_cancel
            with self._jobs_lock:
                for sess in list(self._job_sessions.values()):
                    sess.request_cancel(rollback=hard_reset)
            request_cancel(rollback=hard_reset)
            return {"success": True, "cancelled_count": len(cancelled_ids)}
        except Exception as e:
            return {"success": False, "error": str(e)}


    def finalizePipeline(self, data):
        try:
            if isinstance(data, str):
                input_dir = data
                final_name = ""
            elif isinstance(data, dict):
                input_dir = data.get("inputPath", "")
                final_name = data.get("finalName", "")
            else:
                return {"success": False, "error": "No input path"}

            if not input_dir: 
                return {"success": False, "error": "No input path"}
            
            from src.utils.txt_sync import sync_chapter_txt
            res = sync_chapter_txt(input_dir, final_name or None)
            return res
        except Exception as e:
            return {"success": False, "error": str(e)}


