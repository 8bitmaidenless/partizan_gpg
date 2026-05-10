from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from partizan_gpg.tui.settings import AppSettings


@dataclass
class GenerateKeyResult:
    name: str
    email: str
    algorithm: str
    expire: str
    passphrase: str | None
    cancelled: bool = False

    @classmethod
    def from_cancel(cls) -> "GenerateKeyResult":
        return cls(
            name="",
            email="",
            algorithm="rsa",
            expire="2y",
            passphrase=None,
            cancelled=True
        )

    @property
    def was_empty_passphrase(self) -> bool:
        return not bool(self.passphrase)
    

class GenerateKeyModal(ModalScreen[GenerateKeyResult]):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    #gkm-outer {
        align: center middle;
        height: 100%;
        width: 100%;
    }
    #gkm-inner {
        width: 56;
        height: auto;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }
    #gkm-title {
        text-style: bold;
        color: $text;
        margin-bottom: 0;
    }
    #gkm-divider {
        color: $primary;
        margin-bottom: 1;
    }
    .gkm-label {
        color: $text-muted;
        margin-top: 1;
        margin-bottom: 0;
    }

    #gkm-name,
    #gkm-email,
    #gkm-passphrase {
        width: 100%;
        border: tall $primary-darken-1;
        margin-bottom: 0;
    }

    #gkm-name:focus,
    #gkm-email:focus,
    #gkm-passphrase:focus {
        border: tall $primary;
    }

    #gkm-algo,
    #gkm-expire {
        width: 100%;
        border: tall $primary-darken-1;
        margin-bottom: 0;
    }
    #gkm-hint {
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
    }
    #gkm-buttons {
        layout: horizontal;
        height: auto;
        align: right middle;
        width: 100%;
        margin-top: 1;
    }
    #gkm-buttons Button {
        margin-left: 1;
        min-width: 12;
    }
    """

    _ALGO_OPTIONS = [
        ("RSA 4096", "rsa"),
        ("ECC (Ed25519/Cv25519)", "ecc"),
    ]
    _EXPIRE_OPTIONS = [
        ("Never", "0"),
        ("1 year", "1y"),
        ("2 years", "2y"),
        ("5 years", "5y"),
    ]

    def __init__(self, app_settings: AppSettings, **kwargs) -> None:
        super().__init__(**kwargs)
        self._default_algo = app_settings.algorithm 
        self._default_expiry = app_settings.expire


    def compose(self) -> ComposeResult:
        with Container(id="gkm-outer"):
            with Vertical(id="gkm-inner"):
                yield Label("Generate New Key", id="gkm-title")
                yield Static("-" * 38, id="gkm-divider")

                yield Label("Name", classes="gkm-label")
                yield Input(
                    placeholder="Alice Example",
                    id="gkm-name"
                )

                yield Label("Email", classes="gkm-label")
                yield Input(
                    placeholder="alice@example.com",
                    id="gkm-email"
                )

                yield Label("Algorithm", classes="gkm-label")
                yield Select(
                    self._ALGO_OPTIONS,
                    value=self._default_algo,
                    id="gkm-algo",
                    allow_blank=False
                )

                yield Label("Expiry", classes="gkm-label")
                yield Select(
                    self._EXPIRE_OPTIONS,
                    value=self._default_expiry,
                    id="gkm-expire",
                    allow_blank=False
                )

                yield Label("Passphrase (optional)", classes="gkm-label")
                yield Input(
                    placeholder="leave blank for *no* passphrase",
                    password=True,
                    id="gkm-passphrase"
                )

                yield Static(
                    " Empty passphrase = unprotected secret key.",
                    id="gkm-hint"
                )

                with Horizontal(id="gkm-buttons"):
                    yield Button("Generate", variant="primary", id="gkm-ok")
                    yield Button("Cancel", variant="default", id="gkm-cancel")

    def on_mount(self) -> None:
        self.query_one("#gkm-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gkm-ok":
            self._submit()
        else:
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "gkm-passphrase":
            self._submit()
        
    def action_cancel(self) -> None:
        self.dismiss(GenerateKeyResult.from_cancel())

    def _submit(self) -> None:
        name = self.query_one("#gkm-name", Input).value.strip()
        email = self.query_one("#gkm-email", Input).value.strip()
        algo = self.query_one("#gkm-algo", Select).value
        expire = self.query_one("#gkm-expire", Select).value
        passphrase = self.query_one("#gkm-passphrase", Input).value

        if not name:
            self.query_one("#gkm-name", Input).focus()
            self.notify("Name is required.", severity="warning")
            return
        if not email or "@" not in email:
            self.query_one("#gkm-email", Input).focus()
            self.notify(
                "A valid email address is required.",
                severity="warning"
            )
            return
        
        self.dismiss(GenerateKeyResult(
            name=name,
            email=email,
            algorithm=str(algo),
            expire=str(expire),
            passphrase=passphrase or None
        ))