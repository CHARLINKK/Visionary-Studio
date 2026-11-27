import importlib

from src.model_engines.core_installer.dependency_probe import (
    _cache_lock,
    build_pip_install_args,
    check_ai_dependencies,
    detect_cuda_target,
    get_cuda_recommendation,
    has_nvidia_gpu,
    measure_torch_footprint_bytes,
)

_LAZY_EXPORTS = {
    "run_pip_install_worker": ("src.model_engines.core_installer.pip_runner", "run_pip_install_worker"),
    "run_pip_uninstall_worker": ("src.model_engines.core_installer.uninstaller", "run_pip_uninstall_worker"),
    "download_wheelhouse_plan": ("src.model_engines.core_installer.wheelhouse_plan", "download_wheelhouse_plan"),
    "inspect_wheels_unpacked_manifest": ("src.model_engines.core_installer.wheelhouse_plan", "inspect_wheels_unpacked_manifest"),
    "measure_site_packages_entries_bytes": ("src.model_engines.core_installer.wheelhouse_plan", "measure_site_packages_entries_bytes"),
    "resolve_pip_install_plan": ("src.model_engines.core_installer.wheelhouse_plan", "resolve_pip_install_plan"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod_name, attr_name = target
    mod = importlib.import_module(mod_name)
    val = getattr(mod, attr_name)
    globals()[name] = val
    return val


__all__ = [
    "_cache_lock",
    "check_ai_dependencies",
    "has_nvidia_gpu",
    "detect_cuda_target",
    "get_cuda_recommendation",
    "build_pip_install_args",
    "measure_torch_footprint_bytes",
    "run_pip_install_worker",
    "run_pip_uninstall_worker",
    "resolve_pip_install_plan",
    "download_wheelhouse_plan",
    "inspect_wheels_unpacked_manifest",
    "measure_site_packages_entries_bytes",
]
