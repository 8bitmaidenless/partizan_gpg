# Makefile - Local PyInstaller helpers
# Run from the repo root. Builds for the CURRENT platform only.
# Cross-platform builds go through Github actions.

.PHONY: install build clean

install:
	poetry install --with dev
	poetry run pip install --upgrade pip && poetry run pip install pyinstaller

build:
	poetry run pyinstaller partizan_gpg.spec

clean:
	rm -rf build dist __pycache__ *.spec.bak