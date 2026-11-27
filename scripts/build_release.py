from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(PROJECT_ROOT, "dist_installer")
DEFAULT_ARCHIVE_SRC = os.path.join(PROJECT_ROOT, "assets", "python", "engine-runtime.tar.zst")
MANIFEST_FILENAME = "engine-runtime.manifest.json"


def load_package_metadata(project_root=PROJECT_ROOT):
    """Lê versão do aplicativo e engineVersion de package.json."""
    pkg_path = os.path.join(project_root, "package.json")
    with open(pkg_path, "r", encoding="utf-8") as fh:
        pkg = json.load(fh)
    app_version = str(pkg.get("version") or "1.0.0")
    engine_version = str(pkg.get("engineVersion") or app_version)
    return {"appVersion": app_version, "engineVersion": engine_version}


def compute_sha256(file_path, chunk_size=4 * 1024 * 1024):
    """Calcula SHA-256 em streaming para arquivos grandes sem pressionar a RAM."""
    digest = hashlib.sha256()
    with open(file_path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def generate_engine_manifest(archive_path, dist_dir, engine_version, app_version="1.0.0"):
    """Gera o manifesto sidecar engine-runtime.manifest.json ao lado do instalador."""
    os.makedirs(dist_dir, exist_ok=True)
    stat = os.stat(archive_path)
    manifest = {
        "schemaVersion": 1,
        "appVersion": str(app_version),
        "engineVersion": str(engine_version),
        "archiveName": os.path.basename(archive_path),
        "size": stat.st_size,
        "sha256": compute_sha256(archive_path),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = os.path.join(dist_dir, MANIFEST_FILENAME)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return manifest_path, manifest


def check_prerequisites():
    """Verifica se Node.js/npm estão disponíveis para o pipeline canônico Electron."""
    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd")
    node_cmd = shutil.which("node") or shutil.which("node.exe")
    return {
        "npm": npm_cmd,
        "node": node_cmd,
    }


def copy_engine_runtime_archive(
    archive_src=DEFAULT_ARCHIVE_SRC,
    dist_dir=DIST_DIR,
    require_engine=False,
    project_root=PROJECT_ROOT,
):
    """Assegura que engine-runtime.tar.zst e seu manifesto acompanhem o instalador Electron."""
    if not os.path.exists(archive_src):
        msg = (
            f"Pacote de runtime não encontrado em {archive_src}. "
            "Sem ele ao lado do Setup.exe, o usuário precisará selecionar o arquivo manualmente no 1º boot."
        )
        if require_engine:
            raise FileNotFoundError(msg)
        print(f"⚠️ [AVISO] {msg}")
        return None

    os.makedirs(dist_dir, exist_ok=True)
    archive_dst = os.path.join(dist_dir, os.path.basename(archive_src))

    src_stat = os.stat(archive_src)
    need_copy = True
    if os.path.exists(archive_dst):
        dst_stat = os.stat(archive_dst)
        if dst_stat.st_size == src_stat.st_size and int(dst_stat.st_mtime) == int(src_stat.st_mtime):
            need_copy = False

    if need_copy:
        shutil.copy2(archive_src, archive_dst)
        print(f"📦 Copiado {os.path.basename(archive_src)} -> {archive_dst}")
    else:
        print(f"📦 Sidecar atualizado reaproveitado em {archive_dst}")

    meta = load_package_metadata(project_root)
    manifest_path, manifest = generate_engine_manifest(
        archive_dst,
        dist_dir,
        engine_version=meta["engineVersion"],
        app_version=meta["appVersion"],
    )
    print(f"🧾 Manifesto gerado: {manifest_path} (engineVersion={manifest['engineVersion']})")
    return archive_dst


def precompile_src_bytecode(project_root=PROJECT_ROOT):
    """
    Limpa __pycache__ antigos e pré-compila todo o diretório src/ usando PEP 552 (CHECKED_HASH).
    Usar CHECKED_HASH em vez de mtime garante que o Python reutilize os .pyc empacotados
    mesmo após o instalador NSIS alterar os timestamps dos arquivos .py na máquina do usuário.
    """
    src_dir = os.path.join(project_root, "src")
    if not os.path.isdir(src_dir):
        return 0

    for root, dirs, _files in os.walk(src_dir):
        if "__pycache__" in dirs:
            pycache_path = os.path.join(root, "__pycache__")
            shutil.rmtree(pycache_path, ignore_errors=True)
            dirs.remove("__pycache__")

    engine_py = os.path.join(project_root, "engine", "python.exe")
    if os.path.isfile(engine_py) and os.path.abspath(engine_py) != os.path.abspath(sys.executable):
        code = (
            "import compileall, py_compile, sys; "
            "ok = compileall.compile_dir(sys.argv[1], force=True, quiet=1, "
            "invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH); "
            "sys.exit(0 if ok else 1)"
        )
        subprocess.run([engine_py, "-c", code, src_dir], cwd=project_root, check=True)
    else:
        import compileall
        import py_compile

        ok = compileall.compile_dir(
            src_dir,
            force=True,
            quiet=1,
            invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH,
        )
        if not ok:
            raise RuntimeError(f"Falha ao pré-compilar bytecode em {src_dir}")

    pyc_count = 0
    for root, _dirs, files in os.walk(src_dir):
        if os.path.basename(root) == "__pycache__":
            pyc_count += sum(1 for f in files if f.endswith(".pyc"))
    print(f"⚡ Bytecode Python pré-compilado (CHECKED_HASH): {pyc_count} arquivos .pyc em {src_dir}")
    return pyc_count


def build_electron_release(target_script="dist:installer", require_engine=False, finalize_only=False):
    """Executa o pipeline único e canônico de build (bytecode .pyc + Vite UI + electron-builder + manifesto sidecar)."""
    precompile_src_bytecode(PROJECT_ROOT)
    if not finalize_only:
        prereqs = check_prerequisites()
        npm_bin = prereqs.get("npm")
        if not npm_bin:
            raise RuntimeError("Utilitário 'npm' não encontrado no PATH do sistema. Instale o Node.js v18+.")

        print(f"🚀 Executando pipeline canônico Electron ({target_script})...")
        subprocess.run([npm_bin, "run", target_script], cwd=PROJECT_ROOT, check=True)

    copy_engine_runtime_archive(require_engine=require_engine)
    print(f"✅ Build concluído com sucesso em: {DIST_DIR}")


if __name__ == "__main__":
    if "--all" in sys.argv:
        target = "dist:all"
    elif "--portable" in sys.argv:
        target = "dist:portable"
    else:
        target = "dist:installer"

    require_engine = "--require-engine" in sys.argv
    finalize_only = "--finalize-only" in sys.argv

    try:
        build_electron_release(target, require_engine=require_engine, finalize_only=finalize_only)
    except subprocess.CalledProcessError as exc:
        print(f"❌ Falha durante o empacotamento Electron (código {exc.returncode}).")
        sys.exit(exc.returncode or 1)
    except Exception as exc:
        print(f"❌ Erro no build: {exc}")
        sys.exit(1)
