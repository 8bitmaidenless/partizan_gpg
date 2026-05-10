import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLERS_DIR = Path(__file__).resolve().parent


def detect_platform() -> str:
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    else:
        return "linux"
    

def run_pyinstaller() -> bool:
    spec_file = INSTALLERS_DIR / "partizan_gpg.spec"
    if not spec_file.exists():
        print(f"[ERROR] PyInstaller spec not found: {spec_file}")
        return False
    
    print(f"[INFO] Running PyInstaller...")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(spec_file),
            "--distpath",
            str(INSTALLERS_DIR / "dist"),
            "--workpath",
            str(INSTALLERS_DIR / "build"),
            "--noconfirm",
        ],
        cwd=str(PROJECT_ROOT)
    )
    if result.returncode != 0:
        print(f"[ERROR] PyInstaller build failed.")
        return False
    
    print("[OK] PyInstaller build successful.")
    return True


def build_windows_installer() -> bool:
    nsi_file = INSTALLERS_DIR / "windows" / "partizan_gpg.nsi"
    if not nsi_file.exists():
        print("[ERROR] NSIS script not found.")
        return False
    
    print("[INFO] Building Windows NSIS installer...")
    result = subprocess.run(
        ["makensis", str(nsi_file)],
        cwd=str(INSTALLERS_DIR / "windows")
    )
    return result.returncode == 0


def build_macos_dmg() -> bool:
    script = INSTALLERS_DIR / "macos" / "build_dmg.sh"
    if not script.exists():
        print("[ERROR] macOS build script not found.")
        return False
    
    print("[INFO] Building macOS dmg...")
    result = subprocess.run(["bash", str(script)], cwd=str(INSTALLERS_DIR / "macos"))
    return result.returncode == 0


def build_linux_appimage() -> bool:
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux", "auto"],
        default="auto",
        help="Target platform"
    )
    args = parser.parse_args()

    platform = args.platform if args.platform != "auto" else detect_platform()
    print(f"[INFO] Building for platform: {platform}")
    print(f"[INFO] Project root: {PROJECT_ROOT}")

    if platform == "windows":
        success = build_windows_installer()
    elif platform == "macos":
        success = build_macos_dmg()
    elif platform == "linux":
        success = build_linux_appimage()
    else:
        print(f"[ERROR] Unknown platform: {platform}")
        sys.exit(1)
    
    if success:
        print(f"[OK] {platform} installer built successfully")
    else:
        print(f"[ERROR] {platform} installer build failed")
        sys.exit(1)


if __name__ == "__main__":
    main()