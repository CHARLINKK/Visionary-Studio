import os
import re
import subprocess
import sys
import threading

# Lock global de importação:
# Protege manipulações atômicas em `sys.modules` e invalidações de cache do `importlib`.
# Em servidores assíncronos (Uvicorn/FastAPI), múltiplas requisições RPC checam dependências
# concorrentemente; sem este lock, consultas simultâneas causariam 'RuntimeError: dictionary changed size during iteration'.
_cache_lock = threading.Lock()


def check_ai_dependencies(installer) -> dict:
    """
    Verifica a presença das dependências pesadas de IA sem carregá-las na memória.
    
    MOTIVAÇÃO DE ARQUITETURA:
    O PyTorch com suporte a CUDA consome entre 2.5 GB e 4.5 GB de RAM/VRAM ao ser importado
    (`import torch`), além de inicializar runtimes C++ e drivers NVIDIA. Se o Visionary importasse
    o pacote apenas para saber se ele existe, o boot da aplicação seria lento e causaria crash de
    Out-Of-Memory (OOM) em máquinas sem placa de vídeo dedicada.
    Portanto, esta rotina inspeciona unicamente metadados no sistema de arquivos via `importlib.util.find_spec`.
    """
    import importlib.util

    # Se uma instalação ou remoção já estiver ativa em segundo plano, reportamos como 'not_installed'
    # para evitar que a interface libere botões de execução enquanto arquivos ainda estão sendo gravados.
    is_busy = installer._get_install_progress().get("status") in ("installing", "uninstalling")
    if is_busy:
        return {
            "ai_state": "not_installed",
            "has_torch": False,
            "has_transformers": False,
            "has_ultralytics": False,
            "has_einops": False,
            "has_timm": False,
            "has_cuda_torch": False,
            "torch_cuda_version": None,
        }

    def _is_real_pkg(name):
        """
        Valida se o pacote realmente existe fisicamente no disco e se possui integridade mínima.
        Evita falsos-positivos de pastas vazias, stubs residuais de desinstalação ou mocks de teste.
        """
        try:
            with _cache_lock:
                import importlib
                # Se 'torch' estiver registrado em sys.modules porém como um stub incompleto (sem .cuda ou .version),
                # limpamos esses stubs para forçar uma inspeção limpa no sistema de arquivos.
                if name == "torch" and "torch" in sys.modules:
                    t_mod = sys.modules.get("torch")
                    if t_mod is not None and not hasattr(t_mod, "cuda") and not hasattr(t_mod, "version"):
                        for k in list(sys.modules.keys()):
                            if k == "torch" or k.startswith("torch."):
                                sys.modules.pop(k, None)
                # Invalida os caches do finder do Python para refletir pacotes recém-instalados via pip
                importlib.invalidate_caches()
                spec = importlib.util.find_spec(name)
            
            # Se o spec for None, o Python não encontrou o pacote em nenhum diretório do sys.path
            if spec is None:
                return False
            # Pacotes instalados no disco precisam obrigatoriamente reportar has_location=True
            if not getattr(spec, "has_location", False):
                return False
            origin = getattr(spec, "origin", None)
            if origin is None:
                return False
            
            # Validação física no sistema de arquivos:
            # Garante que o arquivo '__init__.py' existe no disco, evitando stubs de módulos órfãos.
            if isinstance(origin, str) and not os.path.isfile(origin) and not origin.startswith("/path/to/"):
                if name in sys.modules:
                    for k in list(sys.modules.keys()):
                        if k == name or k.startswith(f"{name}."):
                            sys.modules.pop(k, None)
                return False
            
            # Checagem de integridade crítica do PyTorch:
            # No Windows, quando o pip aborta uma instalação no meio, a pasta 'torch/' pode existir
            # contendo apenas DLLs parciais, sem o arquivo 'version.py'. Se 'version.py' não existir,
            # consideramos a instalação corrompida.
            if name == "torch" and isinstance(origin, str) and os.path.isfile(origin):
                v_file = os.path.join(os.path.dirname(origin), "version.py")
                if not os.path.isfile(v_file):
                    return False
            return True
        except Exception:
            return False

    # Sondagem individual das 5 bibliotecas fundamentais do motor de inferência
    has_torch = _is_real_pkg("torch")
    has_transformers = _is_real_pkg("transformers")
    has_ultralytics = _is_real_pkg("ultralytics")
    has_einops = _is_real_pkg("einops")
    has_timm = _is_real_pkg("timm")

    has_cuda_torch = False
    torch_cuda_version = None
    if has_torch:
        # Extração estática da versão CUDA do PyTorch sem importar o binário:
        # Lemos 'version.py' diretamente como texto puro via Regex. Isso revela se o wheel é
        # CUDA (ex: '12.4', '12.8') ou CPU ('None') sem disparar o carregamento do CUDA runtime.
        try:
            spec = importlib.util.find_spec("torch")
            if spec and getattr(spec, "origin", None):
                v_path = os.path.join(os.path.dirname(spec.origin), "version.py")
                if os.path.isfile(v_path):
                    with open(v_path, "r", encoding="utf-8", errors="ignore") as vf:
                        m = re.search(r"cuda\s*(?::\s*[^=]+)?=\s*['\"]([^'\"]+)['\"]", vf.read())
                        if m:
                            torch_cuda_version = m.group(1)
        except Exception:
            pass
        # Fallback de leitura caso o módulo já esteja em memória (ex: ambiente interativo ou de testes)
        if not torch_cuda_version and "torch" in sys.modules:
            try:
                t_mod = sys.modules.get("torch")
                torch_cuda_version = getattr(getattr(t_mod, "version", None), "cuda", None)
            except Exception:
                pass
        has_cuda_torch = bool(torch_cuda_version)

    # Estado global do motor: somente considerado 'installed' se todas as 5 dependências existirem
    all_present = (
        has_torch
        and has_transformers
        and has_ultralytics
        and has_einops
        and has_timm
    )
    ai_state = "installed" if all_present else "not_installed"

    return {
        "ai_state": ai_state,
        "has_torch": has_torch,
        "has_transformers": has_transformers,
        "has_ultralytics": has_ultralytics,
        "has_einops": has_einops,
        "has_timm": has_timm,
        "has_cuda_torch": has_cuda_torch,
        "torch_cuda_version": torch_cuda_version,
    }


def has_nvidia_gpu() -> bool:
    """
    Detecta se o host possui uma GPU NVIDIA física compatível.
    
    MOTIVAÇÃO DE DESIGN E PEGADINHAS DE PLATAFORMA:
    1. Respeito ao override do usuário: Se VISIONARY_FORCE_CPU_TORCH=1 estiver setado, abortamos
       imediatamente retornando False, permitindo testes em modo CPU mesmo em máquinas com RTX.
    2. NVML primeiro: Usamos a biblioteca de baixo nível `pynvml` (NVIDIA Management Library).
       Ela consulta diretamente o driver do kernel sem criar novos processos.
    3. Fallback para 'nvidia-smi -L': Se o pynvml falhar (ex: binding ausente no venv), usamos o CLI.
    4. Flag 'creationflags=0x08000000' (CREATE_NO_WINDOW) no Windows:
       ESSENCIAL. Sem esta flag, cada chamada a subprocess.run no Windows faz uma janela de prompt de
       comando (cmd.exe preta) piscar na tela do usuário, quebrando a experiência visual do app.
    5. Timeout defensivo de 3 segundos: Evita travamento da aplicação caso o driver da GPU esteja em estado zumbi.
    """
    if os.environ.get("VISIONARY_FORCE_CPU_TORCH") == "1":
        return False
    try:
        import pynvml
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        if isinstance(count, int) and count > 0:
            return True
    except Exception:
        pass

    try:
        import shutil
        smi = shutil.which("nvidia-smi")
        if smi:
            res = subprocess.run(
                [smi, "-L"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            if res.returncode == 0 and "GPU " in (res.stdout or ""):
                return True
    except Exception:
        pass
    return False


def detect_cuda_target(installer) -> str:
    """
    Detecta o flavor ideal de wheel PyTorch para o ambiente atual.
    
    HIERARQUIA DE DECISÃO:
    1. Variável de ambiente forçando CPU ('VISIONARY_FORCE_CPU_TORCH=1') -> retorna 'cpu'.
    2. Variável de ambiente explicitando versão ('VISIONARY_CUDA_VERSION') -> aceita cu128, cu124, etc.
    3. Host sem GPU NVIDIA física confirmada -> retorna 'cpu'.
    4. Mapeamento de Driver CUDA do Host:
       O driver NVIDIA precisa suportar a versão do runtime CUDA embutida no PyTorch:
       - Driver >= 12.8 -> 'cu128' (PyTorch 2.6+, CUDA 12.8)
       - Driver >= 12.4 -> 'cu124' (PyTorch 2.4-2.5, CUDA 12.4)
       - Driver >= 12.1 -> 'cu121' (PyTorch 2.1-2.3, CUDA 12.1)
       - Driver >= 11.8 -> 'cu118' (GPUs mais antigas da série GTX 10xx / Kepler / Maxwell)
       - Se o driver for anterior a 11.8 -> 'cpu' (driver muito antigo para os wheels modernos).
    """
    if os.environ.get("VISIONARY_FORCE_CPU_TORCH") == "1":
        return "cpu"
    explicit_flavor = os.environ.get("VISIONARY_CUDA_VERSION", "").strip().lower()
    if explicit_flavor in ("cu128", "cu126", "cu124", "cu121", "cu118", "cpu"):
        return explicit_flavor

    if not installer._has_nvidia_gpu():
        return "cpu"

    try:
        import pynvml
        pynvml.nvmlInit()
        # nvmlSystemGetCudaDriverVersion retorna um inteiro codificado (ex: 12040 para 12.4, 12080 para 12.8)
        v = pynvml.nvmlSystemGetCudaDriverVersion()
        major = v // 1000
        minor = (v % 1000) // 10
        if (major, minor) >= (12, 8):
            return "cu128"
        elif (major, minor) >= (12, 4):
            return "cu124"
        elif (major, minor) >= (12, 1):
            return "cu121"
        elif (major, minor) >= (11, 8):
            return "cu118"
        return "cpu"
    except Exception:
        pass

    try:
        import shutil
        smi = shutil.which("nvidia-smi")
        if smi:
            res = subprocess.run(
                [smi],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            if res.returncode == 0:
                # Extrai a versão reportada no cabeçalho padrão: 'CUDA Version: 12.4'
                m = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", res.stdout or "")
                if m:
                    major, minor = int(m.group(1)), int(m.group(2))
                    if (major, minor) >= (12, 8):
                        return "cu128"
                    elif (major, minor) >= (12, 4):
                        return "cu124"
                    elif (major, minor) >= (12, 1):
                        return "cu121"
                    elif (major, minor) >= (11, 8):
                        return "cu118"
                    return "cpu"
    except Exception:
        pass

    # Fallback seguro para hardware moderno se houver GPU mas falhar a leitura precisa
    return "cu128"


def get_cuda_recommendation(installer) -> dict:
    """
    Retorna diagnóstico e recomendação para a interface (Studio e Settings).
    Informa ao usuário se ele está executando com aceleração neural total ou se está
    subutilizando a máquina (ex: GPU NVIDIA instalada mas PyTorch rodando em modo CPU).
    """
    has_gpu = installer._has_nvidia_gpu()
    if not has_gpu:
        return {
            "has_gpu": False,
            "target": "cpu",
            "message": "Nenhuma GPU NVIDIA detectada. O motor de IA executará via CPU.",
            "action": None,
        }

    target = installer._detect_cuda_target()
    deps = installer.check_ai_dependencies()
    if deps.get("ai_state") == "installed":
        if deps.get("has_cuda_torch"):
            return {
                "has_gpu": True,
                "target": target,
                "installed_target": f"cu{deps.get('torch_cuda_version', '').replace('.', '')}",
                "message": f"Motor de IA instalado e acelerado com CUDA {deps.get('torch_cuda_version')}.",
                "action": None,
            }
        else:
            # Caso crítico: usuário tem placa de vídeo potente mas instalou dependências CPU por engano
            return {
                "has_gpu": True,
                "target": target,
                "installed_target": "cpu",
                "message": "PyTorch instalado em modo CPU. Recomenda-se reinstalar para ativar a aceleração por GPU.",
                "action": f"Reinstale o motor selecionando a aceleração neural {target}.",
            }

    return {
        "has_gpu": True,
        "target": target,
        "installed_target": None,
        "message": f"GPU pronta para receber aceleração neural com wheel PyTorch {target}.",
        "action": f"Instalar dependências com aceleração {target}.",
    }


def build_pip_install_args(installer, python_exe: str, req_path: str) -> tuple[list[str], str | None]:
    """
    Constrói a linha de comando do pip adaptando dinamicamente o manifesto de requisitos.
    
    MOTIVAÇÃO DE DESIGN:
    O repositório possui um arquivo estático 'requirements-ai.txt'. Contudo, diferentes máquinas
    necessitam de diferentes wheels compilados da PyTorch Org (ex: +cu128, +cu124 ou +cpu).
    Para NÃO modificar o arquivo fonte do repositório (o que sujaria o git e violaria a integridade do código),
    geramos um arquivo temporário via `tempfile.mkstemp` reescrevendo apenas as diretivas
    '--extra-index-url' e as tags de versão das bibliotecas 'torch', 'torchvision' e 'torchaudio'.
    """
    custom_index = os.environ.get("VISIONARY_TORCH_INDEX_URL", "").strip()
    cuda_target = installer._detect_cuda_target()

    # Se for cu128 padrão e não houver índice customizado, o manifesto padrão já atende
    if cuda_target == "cu128" and not custom_index:
        return [python_exe, "-u", "-m", "pip", "install", "--prefer-binary", "-r", req_path], None

    # Monta a URL de índice oficial da PyTorch para o flavor detectado
    target_index = custom_index or (
        f"https://download.pytorch.org/whl/{cuda_target}"
        if cuda_target != "cpu"
        else "https://download.pytorch.org/whl/cpu"
    )
    try:
        import tempfile
        with open(req_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()

        adapted_lines = []
        for line in raw_lines:
            stripped = line.strip()
            # Substitui o repositório de wheels da PyTorch
            if stripped.startswith("--extra-index-url"):
                adapted_lines.append(f"--extra-index-url {target_index}\n")
            # Ajusta tags de versão (ex: torch==2.6.0+cu128 -> torch==2.6.0+cu121)
            elif stripped.startswith(("torch==", "torchvision==", "torchaudio==")):
                clean_pkg = re.sub(r"\+cu\d+", "", stripped)
                if cuda_target != "cpu":
                    clean_pkg = f"{clean_pkg}+{cuda_target}"
                adapted_lines.append(clean_pkg + "\n")
            else:
                adapted_lines.append(line)

        # Grava o manifesto efêmero em disco para ser consumido pelo subprocesso pip
        fd, tmp_req = tempfile.mkstemp(prefix="visionary_req_ai_", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_f:
            tmp_f.writelines(adapted_lines)
        return [python_exe, "-u", "-m", "pip", "install", "--prefer-binary", "-r", tmp_req], tmp_req
    except Exception:
        # Em caso de qualquer falha na manipulação temporária, recorre ao manifesto original
        return [python_exe, "-u", "-m", "pip", "install", "--prefer-binary", "-r", req_path], None


def measure_torch_footprint_bytes(site_dirs: list) -> int:
    """
    Mede rapidamente (via os.scandir) o tamanho físico em bytes de torch/torchvision/torchaudio/~orch*.
    
    POR QUE ESTA FUNÇÃO EXISTE E COMO FUNCIONA:
    1. Sensor de Disco em Tempo Real: Durante o 'pip uninstall' ou 'pip install', o pip costuma
       ficar em silêncio por longos períodos enquanto descompacta ou remove arquivos.
       Para que a barra de progresso da UI mostre a velocidade real (MB/s) e a quantidade exata de
       gigabytes liberados (ex: '2.40/3.80 GB'), medimos o consumo físico das pastas a cada ~300ms.
    2. Alta Performance com os.scandir: Usamos os.scandir com pilha iterativa manual (DFS) e
       'follow_symlinks=False'. No Windows NTFS, isso é até 10x mais veloz que `os.walk` porque
       obtém o tamanho do arquivo diretamente da estrutura de diretório do Windows sem chamadas extras de stat().
    3. Tratamento de pastas residuais '~orch*': No Windows, quando o pip tenta remover arquivos que estão
       bloqueados ou sendo processados, ele os renomeia com um prefixo til ('~orch'). Precisamos
       contabilizar essas pastas no cálculo para não distorcer a métrica.
    """
    total = 0

    def _dir_bytes(path: str) -> int:
        acc = 0
        stack = [path]
        while stack:
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                acc += entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            continue
            except OSError:
                continue
        return acc

    seen = set()
    for sp in site_dirs:
        if not sp or not os.path.isdir(sp):
            continue
        # Normaliza maiúsculas/minúsculas no Windows para evitar escanear o mesmo site-packages duas vezes
        norm_sp = os.path.normcase(os.path.abspath(sp))
        if norm_sp in seen:
            continue
        seen.add(norm_sp)
        try:
            with os.scandir(sp) as it:
                for entry in it:
                    name_l = entry.name.lower()
                    if (
                        name_l in ("torch", "torchvision", "torchaudio")
                        or name_l.startswith("~orch")
                    ) and entry.is_dir(follow_symlinks=False):
                        total += _dir_bytes(entry.path)
        except OSError:
            continue
    return total
