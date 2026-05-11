import os
import sys
import platform
from pathlib import Path


def get_base_path():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    
    return Path(__file__).resolve().parent


def get_gpg_binary():
    system = platform.system()

    if system == "Darwin":
        from partizan_gpg.cipherlib.macos_shim import activate, bundled_gpg_binary
        activate()
        bundled = bundled_gpg_binary()
        if bundled and bundled.exists():
            return bundled
        return Path("gpg")
    
    base = get_base_path()

    if system == "Windows":
        return base / "bundled" / "windows" / "gnupg" / "bin" / "gpg.exe"
    
    if system == "Linux":
        return base / "bundled" / "linux" / "gpg"
    
    raise RuntimeError(f"Unsupported OS: {system}")