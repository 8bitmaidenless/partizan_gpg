"""
screens/config_settings.py
--------------------------

Layout
------
    ┌──────────────────────────────────────────────────────────┐
    │  Header                                                  │
    ├──────────────────────────────────────────────────────────┤
    │  #ss-scroll  (ScrollableContainer, full height)          │
    │                                                          │
    │  ── GPG ENVIRONMENT ──────────────────────────────────── │
    │  GNUPGHOME path   [ Input                             ]  │
    │                   [ status label                      ]  │
    │                                                          │
    │  ── GPG BINARY ───────────────────────────────────────── │
    │  Binary           [ Input                             ]  │
    │                   [ status label                      ]  │
    │                                                          │
    │  ── KEY GENERATION DEFAULTS ──────────────────────────── │
    │  Algorithm        [ Select: RSA 4096 / ECC Ed25519    ]  │
    │  Default expiry   [ Select: Never / 1y / 2y / 5y      ]  │
    │                                                          │
    │  ── ABOUT ────────────────────────────────────────────── │
    │  Config file path  (read-only label)                     │
    │                                                          │
    │  [ Save ]   [ Discard ]                                  │
    ├──────────────────────────────────────────────────────────┤
    │  Footer                                                  │
    └──────────────────────────────────────────────────────────┘

Messages
--------
    ConfigScreen.Saved(new_settings)
        Posted on the app *before* pop_screen() so GPGApp can rebuild
        its shared gpg instance and update the subtitle.
        
Bindings
--------
    S / Enter    Save and go back
    Escape / D   Discard and go back
    Q            Quit
"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static
)

from partizan_gpg.tui.settings import AppSettings, CONFIG_FILE, save_settings


_CSS_DIR = Path(__file__).parent.parent / "css"

_ALGO_OPTIONS: list[tuple[str, str]] = [
    ("RSA 4096", "rsa"),
    ("ECC (Ed25519 / Cv25519)", "ecc"),
]

_EXPIRE_OPTIONS: list[tuple[str, str]] = [
    ("Never", "0"),
    ("1 year", "1y"),
    ("2 years", "2y"),
    ("5 years", "5y"),
]


class ConfigScreen(Screen):
    """
    Runtime configuration screen.
    
    Receives the *current* AppSettings on construction so inputs are
    pre-populated. Posts `ConfigScreen.Saved` before dismissing so
    GPGApp can rebuild its share gpg instance without requiring a restart.
    
    """
    TITLE = "Settings Configuration"

    CSS_PATH = str(_CSS_DIR / "config_settings.tcss")

    BINDINGS = [
        Binding("s", "save", "Save", show=True, priority=True),
        Binding("d,q", "discard", "Discard", show=True),
    ]

    class Saved(Message):
        """
        Posted on the app immediately before `pop_screen()`.
        GPGApp listens for this and rebuilds self.gpg
        
        """
        def __init__(self, settings: AppSettings) -> None:
            super().__init__()
            self.settings = settings

    def __init__(self, current_settings: AppSettings, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cfg = current_settings

    def compose(self) -> ComposeResult:
        yield Header()
        
        with ScrollableContainer(id="cfg-scroll"):

            yield Static("GPG ENVIRONMENT", classes="cfg-section-label")
            yield Static("-" * 58, classes="cfg-divider")

            with Horizontal(classes="cfg-row"):
                yield Label("GNUPGHOME path", classes="cfg-label")
                with Vertical(classes="cfg-input-col"):
                    yield Input(
                        value=self._cfg.gnupghome,
                        placeholder="leave blank to use the built-in test keyring",
                        id="cfg-gnupghome"
                    )
                    yield Static("", id="cfg-gnupghome-status", classes="cfg-status")

            yield Static("GPG BINARY", classes="cfg-section-label")
            yield Static("-" * 58, classes="cfg-divider")

            with Horizontal(classes="cfg-row"):
                yield Label("Binary name / path", classes="cfg-label")
                with Vertical(classes="cfg-input-col"):
                    yield Input(
                        value=self._cfg.gpg_binary,
                        placeholder="gpg",
                        id="cfg-binary"
                    )
                    yield Static("", id="cfg-binary-status", classes="cfg-status")

            yield Static("KEY GENERATION DEFAULTS", classes="cfg-section-label")
            yield Static("-" * 58, classes="cfg-divider")

            with Horizontal(classes="cfg-row"):
                yield Label("Default algorithm", classes="cfg-label")
                yield Select(
                    _ALGO_OPTIONS,
                    value=self._cfg.algorithm,
                    id="cfg-algo",
                    allow_blank=False
                )

            with Horizontal(classes="cfg-row"):
                yield Label("Default expiry", classes="cfg-label")
                yield Select(
                    _EXPIRE_OPTIONS,
                    value=self._cfg.expire,
                    id="cfg-expire",
                    allow_blank=False
                )

            yield Static("ABOUT", classes="cfg-section-label")
            yield Static("-" * 58, classes="cfg-divider")

            with Horizontal(classes="cfg-row"):
                yield Label("Config file", classes="cfg-label")
                yield Static(str(CONFIG_FILE), classes="cfg-about-value")

            yield Static("", classes="cfg-spacer")
            with Horizontal(id="cfg-buttons"):
                yield Button("Save", variant="primary", id="cfg-btn-save")
                yield Button("Discard", variant="default", id="cfg-btn-discard")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#cfg-gnupghome", Input).focus()

        self._validate_gnupghome()
        self._validate_binary()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "cfg-gnupghome":
            self._validate_gnupghome()
        elif event.input.id == "cfg-binary":
            self._validate_binary()

    def _validate_gnupghome(self) -> None:
        raw = self.query_one("#cfg-gnupghome", Input).value.strip()
        status = self.query_one("#cfg-gnupghome-status", Static)

        if not raw:
            status.update("  → using built-in test keyring (cipherlib default)")
            status.remove_class("cfg-status-err")
            status.add_class("cfg-status-ok")
            return
        
        p = Path(raw).expanduser()
        if p.exists():
            if p.is_dir():
                status.update(f"  ✔ exists: {p.resolve()}")
                status.remove_class("cfg-status-err")
                status.add_class("cfg-status-ok")
            else:
                status.update(f"  ✗ path exists but is not a directory")
                status.remove_class("cfg-status-ok")
                status.add_class("cfg-status-err")
        else:
            status.update(f"  → will be created: {p.resolve()}")
            status.remove_class("cfg-status-err")
            status.add_class("cfg-status-ok")
    
    def _validate_binary(self) -> None:
        import shutil

        raw = self.query_one("#cfg-binary", Input).value.strip() or "gpg"
        status = self.query_one("#cfg-binary-status", Static)

        found = shutil.which(raw)
        if found:
            version = self._read_gpg_version(found)
            if version:
                status.update(f"  ✔ {found}  ({version})")
            else:
                status.update(f"  ✔ {found}")
            status.remove_class("cfg-status-err")
            status.add_class("cfg-status-ok")
        else:
            p = Path(raw)
            if p.exists():
                import os
                if os.access(p, os.X_OK):
                    status.update(f"  ✔ {p.resolve()}")
                    status.remove_class('cfg-status-err')
                    status.add_calss("cfg-status-ok")
                    return
            status.update(f"  ✗ '{raw}' not found on PATH")
            status.remove_class("cfg-status-ok")
            status.add_class("cfg-status-err")

    @staticmethod
    def _read_gpg_version(binary: str) -> str:
        import subprocess
        try:
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                timeout=2,
                text=True
            )
            first_line = result.stdout.splitlines()[0] if result.stdout else ""

            parts = first_line.split()
            if len(parts) >= 3:
                return f"{parts[1].strip('()')} {parts[2]}"
            return first_line.strip()
        except Exception:
            return ""
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cfg-btn-save":
            self.action_save()
        elif event.button.id == "cfg-btn-discard":
            self.action_discard()

    def action_save(self) -> None:
        gnupghome = self.query_one("#cfg-gnupghome", Input).value.strip()
        gpg_binary = self.query_one("#cfg-binary", Input).value.strip() or "gpg"
        algorithm = str(self.query_one("#cfg-algo", Select).value)
        expire = str(self.query_one("#cfg-expire", Select).value)

        new_cfg = AppSettings(
            gnupghome=gnupghome,
            gpg_binary=gpg_binary,
            algorithm=algorithm,
            expire=expire
        )

        ok = save_settings(new_cfg)
        if not ok:
            self.notify(
                f"Could not write settings to:\n{CONFIG_FILE}\n"
                "Check file permissions.",
                title="Save failed",
                severity="error",
                timeout=8
            )
            return
        
        self.app.post_message(self.Saved(new_cfg))
        self.app.pop_screen()

    def action_discard(self) -> None:
        self.app.pop_screen()

