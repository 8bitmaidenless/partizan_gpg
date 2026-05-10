import sys
import os
import subprocess
from pathlib import Path


BASE_PATH = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) != 3:
        raise RuntimeError(f"3 args required: {sys.argv}")

    f1 = str(sys.argv[1]).strip()
    f2 = str(sys.argv[2]).strip()

    f1, f2 = Path(f1), Path(f2)

    files = (Path(f1).resolve(), Path(f2).resolve())

    if any(f.exists() == False for f in files):
        raise ValueError(f"Files not found: {f1} | {f2}")

    command = [
        "diff",
        "--color=always",
        "-u",
        "-B",
        "-b",
        f1.as_posix(),
        f2.as_posix(),
        "|",
        "less",
        "-R"
    ]

    try:
        subprocess.call(
            command,
            shell=True,
            stderr=subprocess.STDOUT
        )
    except Exception as exc:
        print(f"ERROR: {exc}"
        return



if __name__ == "__main__":
    main()
