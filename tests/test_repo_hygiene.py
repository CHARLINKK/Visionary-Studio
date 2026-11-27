import os
import json
import shutil
import subprocess
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_package_json_postinstall_resilience():
    package_json_path = os.path.join(REPO_ROOT, "package.json")
    assert os.path.exists(package_json_path), "package.json must exist"

    with open(package_json_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    scripts = pkg.get("scripts", {})
    postinstall = scripts.get("postinstall", "")

    # Must use cross-platform node runner rather than hardcoded binary execution
    assert "node scripts/postinstall.js" in postinstall

    script_path = os.path.join(REPO_ROOT, "scripts", "postinstall.js")
    assert os.path.exists(script_path), "scripts/postinstall.js must exist"


def test_postinstall_script_runs_cleanly():
    if not shutil.which("node"):
        pytest.skip("Node.js runtime not found in PATH")
    script_path = os.path.join(REPO_ROOT, "scripts", "postinstall.js")
    res = subprocess.run(["node", script_path], cwd=REPO_ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"postinstall.js failed: {res.stderr}"


def test_gitignore_covers_critical_rules():
    gitignore_path = os.path.join(REPO_ROOT, ".gitignore")
    assert os.path.exists(gitignore_path), ".gitignore must exist"

    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_patterns = [
        "dist_installer*",
        "*.zip",
        ".coverage",
        ".visionary_reorder_journal*",
        "logs/*.log",
        "node_modules/",
        "__pycache__/",
    ]

    for pattern in required_patterns:
        assert pattern in content, f".gitignore missing essential pattern: {pattern}"


def test_workspace_root_free_of_orphan_artifacts_and_frontend_shims():
    """
    Garante que pastas de experimentos/legado e arquivos shim órfãos do frontend
    não voltem a poluir a árvore do repositório.
    """
    forbidden_root_entries = [
        "demo_morph_app",
        "restored",
        "dist_release",
        "ORIGINAL_REQUEST.md",
        "TESTAR_DEMO_MORPH.bat",
        "preview.png",
        "preview_biblioteca.png",
        "preview_raw_highlight.png",
        "vite_err.log",
        "vite_out.log",
    ]
    for entry in forbidden_root_entries:
        target = os.path.join(REPO_ROOT, entry)
        assert not os.path.exists(target), f"Artefato órfão encontrado na raiz: {entry}"

    forbidden_frontend_shims = [
        os.path.join("gui", "src", "useWorkspaceStore.js"),
        os.path.join("gui", "src", "components", "LibraryBalloonRow.jsx"),
        os.path.join("gui", "src", "components", "LibraryHeader.jsx"),
        os.path.join("gui", "src", "components", "LibraryScriptView.jsx"),
        os.path.join("gui", "src", "components", "LibrarySidebar.jsx"),
        os.path.join("gui", "src", "components", "LibrarySplitToolbar.jsx"),
        os.path.join("gui", "src", "components", "LibrarySplitView.jsx"),
        os.path.join("gui", "src", "components", "SeamlessInspectorBlock.jsx"),
        os.path.join("gui", "src", "components", "SeamlessLayoutInspector.jsx"),
        os.path.join("gui", "src", "components", "SeamlessOverviewInspector.jsx"),
        os.path.join("gui", "src", "components", "SeamlessSidebar.jsx"),
        os.path.join("gui", "src", "components", "SeamlessTextInspector.jsx"),
        os.path.join("gui", "src", "components", "SeamlessTopbar.jsx"),
    ]
    for rel_shim in forbidden_frontend_shims:
        shim_path = os.path.join(REPO_ROOT, rel_shim)
        assert not os.path.exists(shim_path), f"Shim órfão do frontend não deveria existir: {rel_shim}"
