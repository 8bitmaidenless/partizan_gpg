from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header
from textual.worker import Worker, WorkerState

from partizan_gpg.cipherlib import (
    delete_key,
    export_public_key,
    generate_key,
    import_key_data,
    import_key_file
)
from partizan_gpg.tui.widgets.key_detail import KeyDetailWidget
from partizan_gpg.tui.widgets.key_list import KeyInfo, KeyListWidget
from partizan_gpg.tui.widgets.operation_log import OperationLogWidget
from partizan_gpg.tui.widgets.passphrase_modal import PassphraseModal, PassphraseResult
from partizan_gpg.tui.screens.modals.generate_key_modal import GenerateKeyModal, GenerateKeyResult
from partizan_gpg.tui.screens.modals.import_key_modal import ImportKeyModal, ImportKeyResult
from partizan_gpg.tui.screens.modals.trust_modal import TrustModal, TrustResult
from partizan_gpg.tui.screens.modals.keyserver_modal import KeyserverModal, KeyserverResult


_CSS_DIR = Path(__file__).parent.parent / "css"


class KeyManagementScreen(Screen):
    """
    Full key management interface.
    
    Receives the shared GPG instance from GPGApp and passes it down to 
    every widget and worker that needs it. Never constructs its own GPG 
    instance.
    
    """
    TITLE = "Key Management"

    DEFAULT_CSS = """
#km-body {
    height: 1fr;
    width: 100%;
}

#km-top {
    height: 1fr;
    width: 100%;
}

#km-key-list {
    width: 55%;
}

#km-key-detail {
    width: 45%;
}

#km-op-log {
    height: 10;
    border-top: tall $primary-darken-2;
    background: $background;
}

#gkm-outer {
    align: center middle;
    width: 100%;
    height: 100%;
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

#ikm-outer {
    align: center middle;
    width: 100%;
    height: 100%;
}

#ikm-inner {
    width: 64;
    height: auto;
    max-height: 90%;
    background: $surface;
    border: tall $primary;
    padding: 1 2;
}

#ikm-title {
    text-style: bold;
    color: $text;
    margin-bottom: 0;
}

#ikm-divider {
    color: $primary;
    margin-bottom: 1;
}

.ikm-label {
    color: $text-muted;
    margin-top: 1;
    margin-bottom: 0;
}

#ikm-mode {
    height: auto;
    margin-bottom: 1;
}

#ikm-armor-text {
    height: 10;
    border: tall $primary-darken-1;
    width: 100%;
}

#ikm-armor-text:focus {
    border: tall $primary;
}

#ikm-file-path {
    width: 100%;
    border: tall $primary-darken-1;
}

#ikm-file-path:focus {
    border: tall $primary;
}

#ikm-validation-msg {
    color: yellow;
    height: auto;
    margin-top: 1;
}

#ikm-buttons {
    layout: horizontal;
    height: auto;
    align: right middle;
    width: 100%;
    margin-top: 1;
}

#ikm-buttons Button {
    margin-left: 1;
    min-width: 10;
}

#tm-outer {
    align: center middle;
    width: 100%;
    height: 100%;
}

#tm-inner {
    width: 56;
    height: auto;
    background: $surface;
    border: tall $primary;
    padding: 1 2;
}

#tm-title {
    text-style: bold;
    color: $text;
    margin-bottom: 0;
}

#tm-divider {
    color: $primary;
    margin-bottom: 1;
}

#tm-description {
    color: $text-muted;
    text-style: italic;
    margin-bottom: 1;
}

#tm-trust-set {
    height: auto;
    border: none;
    margin-bottom: 1;
}

#tm-buttons {
    layout: horizontal;
    height: auto;
    align: right middle;
    width: 100%;
    margin-top: 1;
}

#tm-buttons Button {
    margin-left: 1;
    min-width: 12;
}
    """

    BINDINGS = [
        Binding("g", "generate_key", "Generate", show=True),
        Binding("i", "import_key", "Import", show=True),
        Binding("e", "export_key", "Export", show=True),
        Binding("d", "delete_key", "Delete", show=True),
        Binding("t", "set_trust", "Trust", show=True),
        Binding("k", "keyserver", "Keyserver", show=True),
        Binding("s", "save_log", "Save log", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("tab", "cycle_focus", "Switch pane", show=True),
        Binding("q", "go_home", "Home", show=True),
    ]

    def __init__(self, gpg, **kwargs) -> None:
        super().__init__(**kwargs)
        self.gpg = gpg
        self._pending_delete_fp: str | None = None
        self._pending_secret_export_fp: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="km-body"):
            with Horizontal(id="km-top"):
                yield KeyListWidget(gpg=self.gpg, id="km-key-list")
                yield KeyDetailWidget(id="km-key-detail")
            yield OperationLogWidget(id="km-op-log")
        yield Footer()

    def on_mount(self) -> None:
        log = self._log
        log.clear()
        log.log_separator("Key Management")
        log.log(f"keyring: {self.gpg.gnupghome}", level="INFO")

        key_list = self._key_list
        key_list.load(self.gpg)
        log.log(f"{key_list.row_count} key(s) loaded from keyring.", level="INFO")
        key_list.focus()

    def on_screen_resume(self) -> None:
        self._log.clear()
        self._log.log_separator("Key Management")
        self._key_list.refresh_keys(self.gpg)
        self._key_list.focus()
    
    def on_key_list_widget_cursor_moved(
        self,
        event: KeyListWidget.CursorMoved
    ) -> None:
        self._key_detail.show(event.key_info, self.gpg)

    def on_key_list_widget_key_confirmed(
        self,
        event: KeyListWidget.KeyConfirmed
    ) -> None:
        self._key_detail.focus()

    def on_key_detail_widget_export_completed(
        self,
        event: KeyDetailWidget.ExportCompleted
    ) -> None:
        kind = "secret key export" if event.secret else "quick export"
        self._log.log_result(
            ok=event.ok,
            label=kind,
            detail=f"-> {event.path}" if event.ok and event.path else None
        )

    def on_key_detail_widget_secret_export_requested(
        self,
        event: KeyDetailWidget.SecretExportRequested
    ) -> None:
        self._pending_secret_export_fp = event.fingerprint
        self._log.log_separator(
            f"Export secret key: {event.name} <{event.key_id}>"
        )
        self._log.log(
            "⏶ Exporting a secret key.  Keep the output file secure.",
            level="WARN"
        )
        self.app.push_screen(
            PassphraseModal(
                title=f"Passphrase for secret key: {event.name} <{event.key_id}>"
            ),
            callback=self._on_secret_export_pass
        )
    
    def _on_secret_export_pass(self, result: PassphraseResult) -> None:
        fp = self._pending_secret_export_fp
        self._pending_secret_export_fp = None

        if result.cancelled:
            self._log.log("Secret key export cancelled.", level="INFO")
            return
        if result.was_empty:
            self._log.log(
                "Empty passphrase - exporting unprotected secret key.",
                level="WARN"
            )

        self._key_detail.do_export_secret(
            fingerprint=fp,
            passphrase=result.passphrase
        )

    def action_generate_key(self) -> None:
        from partizan_gpg.tui.settings import load_settings
        cfg = load_settings()
        self.app.push_screen(
            GenerateKeyModal(app_settings=cfg),
            callback=self._on_generate_modal_result
        )

    def _on_generate_modal_result(self, result: GenerateKeyResult) -> None:
        if result.cancelled:
            self._log.log("Key generation cancelled.", level="INFO")
            return
        if result.was_empty_passphrase:
            self._log.log(
                "No passphrase provided - secret key will be unprotected.",
                level="WARN"
            )
        self._log.log_separator(f"Generating key for {result.email}")
        self.run_worker(
            self._worker_generate(result),
            thread=True,
            name="generate_key"
        )

    async def _worker_generate(self, result: GenerateKeyResult) -> None:
        fp = await asyncio.to_thread(
            generate_key,
            self.gpg,
            result.name,
            result.email,
            comment="Generated via Partizan Guard GPG",
            expire=result.expire,
            algorithm=result.algorithm,
            passphrase=result.passphrase
        )
        self.app.call_from_thread(
            self._finish_generate,
            fp,
            result.email
        )

    def _finish_generate(self, fp: str | None, email: str) -> None:
        if fp:
            self._log.log_result(
                ok=True,
                label=f"generate_key({email})",
                detail=f"FP: {fp}"
            )
            self._key_list.refresh_keys(self.gpg)
        else:
            self._log.log_result(
                ok=False,
                label=f"generate_key({email})"
            )

    def action_import_key(self) -> None:
        self.app.push_screen(
            ImportKeyModal(),
            callback=self._on_import_modal_result
        )

    def _on_import_modal_result(self, result: ImportKeyResult) -> None:
        if result.cancelled:
            self._log.log("Key import cancelled.", level="INFO")
            return
        self._log.log_separator("Import Key")
        self.run_worker(
            self._worker_import(result),
            thread=True,
            name="import_key"
        )

    async def _worker_import(self, result: ImportKeyResult) -> None:
        if result.mode == "armor":
            fps = await asyncio.to_thread(
                import_key_data,
                self.gpg,
                result.armor_text,
                label="import (armor)"
            )
        else:
            path = Path(result.file_path)
            fps = await asyncio.to_thread(
                import_key_file,
                self.gpg,
                path,
                label=f"import ({path.name})"
            )
        self.app.call_from_thread(self._finish_import, fps)

    def _finish_import(self, fps: list[str]) -> None:
        if fps:
            self._log.log_result(
                ok=True,
                label=f"import key - {len(fps)} key(s) imported",
                detail="; ".join(fp[-16:] for fp in fps)
            )
            self._key_list.refresh_keys(self.gpg)
        else:
            self._log.log_result(
                ok=False,
                label="import key - no keys imported"
            )

    def action_export_key(self) -> None:
        info = self._cursor_key
        if info is None:
            self._log.log(
                "No key selected - move the cursor to a key first.",
                level="WARN"
            )
            return
        self._log.log_separator(f"Export: {info.name}")
        self.run_worker(
            self._worker_export(info),
            thread=True,
            name="export_key"
        )

    async def _worker_export(self, info: KeyInfo) -> None:
        dest = Path.cwd() / f"{info.key_id}.asc"
        data = await asyncio.to_thread(
            export_public_key,
            self.gpg,
            info.fingerprint,
            armor=True,
            output_path=dest
        )
        self.app.call_from_thread(
            self._finish_export,
            bool(data),
            dest
        )

    def _finish_export(self, ok: bool, dest: Path) -> None:
        self._log.log_result(
            ok=ok,
            label="export_public_key",
            detail=f"-> {dest}" if ok else None
        )

    def action_delete_key(self) -> None:
        info = self._cursor_key
        if info is None:
            self._log.log("No key selected.", level="WARN")
            return
        
        self._pending_delete_fp = info.fingerprint
        self.notify(
            f"[i]Delete[/i] key for [b]{info.name}[/b]?\n"
            f"Key ID: [b]{info.key_id}[/b]\n\n"
            "[i]Press [b]Y[/b] to confirm, any other key to cancel.[/i]",
            title="Confirm Deletion",
            severity="warning",
            timeout=10,
            markup=True
        )

    def on_key(self, event) -> None:
        if self._pending_delete_fp is None:
            return
        if event.key.lower() == "y":
            event.stop()
            self._log.log_separator("Delete Key")
            self.app.push_screen(
                PassphraseModal(title="Passphrase required for secret key deletion"),
                callback=self._on_delete_pass
            )
        else:
            self._pending_delete_fp = None
            self._log.log("Deletion cancelled", level="INFO")

    def _on_delete_pass(self, result: PassphraseResult) -> None:
        fp = self._pending_delete_fp
        self._pending_delete_fp = None

        if result.cancelled:
            self._log.log("Key deletion cancelled.", level="INFO")
            return
        if result.was_empty:
            self._log.log("Empty passphrase - only public key may be deleted.", level="WARN")

        self.run_worker(
            self._worker_delete(fp, result),
            thread=True,
            name="delete_key"
        )

    async def _worker_delete(self, fp: str, result: PassphraseResult) -> None:
        ok_sec = await asyncio.to_thread(
            delete_key,
            self.gpg,
            fp,
            secret=True,
            passphrase=result.passphrase
        )
        ok_pub = await asyncio.to_thread(
            delete_key,
            self.gpg,
            fp,
            secret=False,
        )
        self.app.call_from_thread(
            self._finish_delete,
            ok_sec,
            ok_pub,
            fp
        )

    def _finish_delete(self, ok_sec: bool, ok_pub: bool, fp: str) -> None:
        self._log.log_result(
            ok=ok_sec,
            label=f"delete secret key ({fp[-16:]})",
        )
        self._log.log_result(
            ok=ok_pub,
            label=f"delete public key ({fp[-16:]})"
        )

        if ok_pub:
            self._key_detail.clear()
            self._key_list.refresh_keys(self.gpg)

    def action_set_trust(self) -> None:
        info = self._cursor_key
        if info is None:
            self._log.log(
                "No key selected.", 
                level="WARN"
            )
            return
        self.app.push_screen(
            TrustModal(
                key_label=info.name,
                current_trust=info.trust
            ),
            callback=self._on_trust_modal_result
        )

    def _on_trust_modal_result(self, result: TrustResult) -> None:
        if result.cancelled:
            self._log.log(
                "Trust assignment cancelled.",
                level="INFO"
            )
            return
        info = self._cursor_key
        if info is None:
            return
        self._log.log_separator(f"Set Trust: {info.name}")
        self.run_worker(
            self._worker_set_trust(info.fingerprint, result.trust_value),
            thread=True,
            name="set_trust"
        )

    async def _worker_set_trust(self, fp: str, trust_value: str) -> None:
        try:
            await asyncio.to_thread(
                self.gpg.trust_keys,
                fp,
                trust_value
            )
            ok = True
        except Exception:
            ok = False
        self.app.call_from_thread(
            self._finish_trust,
            ok,
            fp,
            trust_value
        )

    def _finish_trust(self, ok: bool, fp: str, trust_value: str) -> None:
        self._log.log_result(
            ok=ok,
            label=f"trust_keys({fp[-16:]}, {trust_value})",
        )
        if ok:
            self._key_list.refresh_keys(self.gpg)
            info = self._cursor_key
            if info:
                self._key_detail.show(info, self.gpg)
                
    def action_keyserver(self) -> None:
        from partizan_gpg.tui.settings import load_settings
        cfg = load_settings()
        cursor = self._cursor_key
        self.app.push_screen(
            KeyserverModal(
                gpg=self.gpg,
                keyserver_url=cfg.keyserver_url_resolved(),
                prefill_fingerprint=cursor.fingerprint if cursor else None
            ),
            callback=self._on_keyserver_result
        )

    def _on_keyserver_result(self, result: KeyserverResult) -> None:
        if result.cancelled:
            self._log.log("Keyserver operation cancelled.", level="INFO")
            return
        
        if result.mode == "search":
            if result.error:
                self._log.log_result(
                    ok=False,
                    label="keyserver fetch",
                    detail=result.error
                )
            elif result.imported_fps:
                self._log.log_result(
                    ok=True,
                    label=f"keyserver fetch - {len(result.imported_fps)} key(s) imported",
                    detail="  ".join(fp[-16:] for fp in result.imported_fps)
                )
                self._key_list.refresh_keys(self.gpg)
            else:
                self._log.log_result(
                    ok=True,
                    label="keyserver fetch - key already in keyring"
                )

        else:
            if result.error:
                self._log.log_result(
                    ok=False,
                    label="keyserver upload",
                    detail=result.error
                )
            else:
                self._log.log_result(
                    ok=True,
                    label=f"keyserver upload - {result.query[-16:]}",
                    detail=(
                        "Verification email sent to each UID address. "
                        "Confirm to make the key searchable by email."
                    )
                )
    
    def action_save_log(self) -> None:
        self._log.save()

    def action_refresh(self) -> None:
        self._log.log("Refreshing keyring...", level="INFO")
        self._key_list.refresh_keys(self.gpg)
        self._log.log(
            f"{self._key_list.row_count} key(s) in keyring.",
            level="INFO"
        )

    def action_cycle_focus(self) -> None:
        focused = self.focused
        if focused and focused.id == "km-key-list":
            self._key_detail.focus()
        else:
            self._key_list.focus()

    def action_go_home(self) -> None:
        self.app.pop_screen()

    @property
    def _log(self) -> OperationLogWidget:
        return self.query_one("#km-op-log", OperationLogWidget)

    @property
    def _key_list(self) -> KeyListWidget:
        return self.query_one("#km-key-list", KeyListWidget)

    @property
    def _key_detail(self) -> KeyDetailWidget:
        return self.query_one("#km-key-detail", KeyDetailWidget)

    @property
    def _cursor_key(self) -> KeyInfo | None:
        return self._key_list.get_cursor_key()

