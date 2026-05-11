from __future__ import annotations

import os
import sys
import atexit
from pathlib import Path


_PLACEHOLDER = Path("/tmp/gnupg_shim")
_shim_active = False


def _bundle_macos_dir() -> Path | None:
    import platform
    if platform.system() != "Darwin":
        return None
    
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent

    candidate = base / "bundled" / "macos"
    return candidate if candidate.exists() else None


def activate() -> bool:
    global _shim_active

    if _shim_active:
        return True
    
    bundle_dir = _bundle_macos_dir()
    if bundle_dir is None:
        return True
    
    try:
        if _PLACEHOLDER.is_symlink():
            current_target = Path(os.readlink(_PLACEHOLDER))
            if current_target == bundle_dir:
                _shim_active = True
                return True
            
            _PLACEHOLDER.unlink()

        elif _PLACEHOLDER.exists():
            print(
                f"[WARN] macos_shim: {_PLACEHOLDER} exists and is not a symlink. "
                "Falling back to system gpg.",
                file=sys.stderr
            )
            return False
        
        _PLACEHOLDER.symlink_to(bundle_dir)
        _shim_active = True

        atexit.register(_deactivate)
        return True
    
    except OSError as exc:
        print(f"[WARN] macos_shim: could not create shim: {exc}", file=sys.stderr)
        return False
    

def _deactivate() -> None:
    global _shim_active
    try:
        if _PLACEHOLDER.is_symlink():
            target = Path(os.readlink(_PLACEHOLDER))
            bundle_dir = _bundle_macos_dir()
            if bundle_dir and target == bundle_dir:
                _PLACEHOLDER.unlink()

    except OSError:
        pass
    _shim_active = False


def bundled_gpg_binary() -> Path | None:
    if not _shim_active:
        activate()
    candidate = _PLACEHOLDER / "bin" / "gpg"
    return candidate if candidate.exists() else None
