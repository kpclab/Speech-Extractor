"""Make pip-installed NVIDIA CUDA DLLs visible to CTranslate2 on Windows."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

# Keep the handles alive for the process lifetime. Closing an add_dll_directory
# handle removes that directory from the Windows DLL search path.
_DLL_DIRECTORY_HANDLES: list[object] = []
_CONFIGURED = False


def configure_windows_cuda_runtime() -> list[Path]:
    """Add NVIDIA wheel ``bin`` folders to PATH and the DLL search path.

    NVIDIA's Windows Python wheels place DLLs in e.g.
    ``site-packages/nvidia/cublas/bin``. CTranslate2 loads cuBLAS lazily,
    therefore these paths must be available before importing/using it.
    Existing system CUDA paths are preserved.
    """
    global _CONFIGURED
    if sys.platform != "win32" or _CONFIGURED:
        return []

    directories: list[Path] = []
    for package in ("nvidia.cublas", "nvidia.cuda_runtime", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(package)
        except (ImportError, ModuleNotFoundError, ValueError):
            spec = None
        if spec is None or not spec.submodule_search_locations:
            continue
        for location in spec.submodule_search_locations:
            bin_dir = Path(location) / "bin"
            if bin_dir.is_dir() and bin_dir not in directories:
                directories.append(bin_dir)

    if directories:
        current_path = os.environ.get("PATH", "")
        prefix = [str(path) for path in directories]
        os.environ["PATH"] = os.pathsep.join(prefix + ([current_path] if current_path else []))

        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            for directory in directories:
                try:
                    _DLL_DIRECTORY_HANDLES.append(add_dll_directory(str(directory)))
                except OSError:
                    # PATH remains configured as a fallback for native loaders.
                    pass

    _CONFIGURED = True
    return directories
