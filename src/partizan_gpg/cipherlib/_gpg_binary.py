import os
import sys
import platform
from pathlib import Path


def get_base_path():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    
    return Path(__file__).resolve().parent


def get_gpg_binary():
    base = get_base_path()
    
    system = platform.system()

    if system == "Windows":
        return base / "bundled" / "windows" / "gnupg" / "bin" / "gpg.exe"
    
    elif system == "Linux":
        return base / "bundled" / "linux" / "gpg"
    
    elif system == "Darwin":
        binary = base / "bundled" / "macos" / "gpg"
        if binary.exists():
            return binary
        return Path("gpg")
    
    raise RuntimeError(f"Unsupported OS: {system}")
