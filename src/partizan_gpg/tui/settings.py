"""
tui/settings.py
---------------
Persistent application settings for Partizan Guard.

Settings are stored as JSON in the platform config directory:
    ~/.config/partizan_gpg/settings.json    (Linux / macOS)
    %APPDATA%\\partizan_gpg\\settings.json (WIndows)

"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _config_dir() -> Path:
    """
    Return the platform-appropriate config directory for this app.
    
    """
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "partizan_gpg"


CONFIG_FILE = _config_dir() / "settings.json"


_DEFAULT_GNUPGHOME: str = ""
_DEFAULT_GPG_BINARY: str = "gpg"
_DEFAULT_ALGORITHM: str = "rsa"
_DEFAULT_EXPIRE: str = "2y"
_DEFAULT_KEYSERVER_URL: str = "https://keys.openpgp.org"


@dataclass
class AppSettings:
    gnupghome: str = field(default=_DEFAULT_GNUPGHOME)
    gpg_binary: str = field(default=_DEFAULT_GPG_BINARY)
    algorithm: str = field(default=_DEFAULT_ALGORITHM)
    expire: str = field(default=_DEFAULT_EXPIRE)
    keyserver_url: str = field(default=_DEFAULT_KEYSERVER_URL)

    def gnupghome_path(self) -> Path | None:
        """
        Return the gnupghome as a resolved Path, or None if unset.
        Expands ~ and env vars.
        """
        if not self.gnupghome.strip():
            return None
        return Path(self.gnupghome).expanduser().resolve()
    
    def gpg_binary_resolved(self) -> str:
        """Return the binary string, falling back to `gpg`."""
        return self.gpg_binary.strip() or _DEFAULT_GPG_BINARY
    
    def keyserver_url_resolved(self) -> str:
        url = self.keyserver_url.strip()
        return url if url else _DEFAULT_KEYSERVER_URL
    
    def build_gpg(self):
        from partizan_gpg.cipherlib import build_gpg as _build_gpg
        return _build_gpg(
            gnupghome=self.gnupghome_path(),
            binary=self.gpg_binary_resolved()
        )
    
    def validate_gnupghome(self) -> tuple[bool, str]:
        """
        Check whether gnupghome is usable.
        
        """
        if not self.gnupghome.strip():
            return True, "Using cipherlib default (test keyring)"
        p = Path(self.gnupghome).expanduser()
        if p.exists():
            if p.is_dir():
                return True, str(p.resolve())
            return False, f"Path exists but is not a directory: {p}"
        return True, f"Will be created: {p.resolve()}"
    
    def validate_gpg_binary(self) -> tuple[bool, str]:
        """
        Check whether the gpg binary is findable on PATH or as an absolute path.
        
        """
        import shutil
        binary = self.gpg_binary_resolved()
        found = shutil.which(binary)
        if found:
            return True, found
        p = Path(binary)
        if p.exists() and os.access(p, os.X_OK):
            return True, str(p.resolve())
        return False, f"'{binary}' not found on PATH"
    
    def validate_keyserver_url(self) -> tuple[bool, str]:
        url = self.keyserver_url_resolved()
        if url.startswith("https://") or url.startswith("http://"):
            return True, url
        return False, f"URL must start with 'https://' or 'http://'  (got: '{url}')"
    

def load_settings() -> AppSettings:
    """
    Load settings from CONFIG_FILE.
     
    Returns AppSettings with defaults for any missing keys.
    Never raises - a missing or malformed file returns clean defaults.
    
    """
    if not CONFIG_FILE.exists():
        return AppSettings()
    
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return AppSettings()
    
    return AppSettings(
        gnupghome=raw.get("gnupghome", _DEFAULT_GNUPGHOME),
        gpg_binary=raw.get("gpg_binary", _DEFAULT_GPG_BINARY),
        algorithm=raw.get("algorithm", _DEFAULT_ALGORITHM),
        expire=raw.get("expire", _DEFAULT_EXPIRE),
        keyserver_url=raw.get("keyserver_url", _DEFAULT_KEYSERVER_URL),
    )


def save_settings(cfg: AppSettings) -> bool:
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(cfg), indent=2, ensure_ascii=False)

        fd, tmp_path = tempfile.mkstemp(
            dir=CONFIG_FILE.parent,
            prefix=".settings_tmp_",
            suffix=".json"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            Path(tmp_path).replace(CONFIG_FILE)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        return True
    except OSError:
        return False