"""
screens/modals/keyserver_modal.py
----------------------------------
KeyserverModal — search for and fetch keys from a keyserver, or upload a
local public key to one.

Supported keyserver API
-----------------------
Default: keys.openpgp.org  (Verifying Keyserver — VKS / Hagrid)
    GET  /vks/v1/by-fingerprint/<40-hex-chars>
    GET  /vks/v1/by-keyid/<16-hex-chars>
    GET  /vks/v1/by-email/<email>
    POST /vks/v1/upload        field: keytext  (armored public key)

Also compatible with HKP keyservers (keyserver.ubuntu.com, etc.) via the
same URL-prefix convention.  The modal sends raw HTTP using only stdlib
(urllib) so there is no external network dependency.

Upload note
-----------
keys.openpgp.org requires the key owner to verify their email address
before the key becomes searchable by email.  After uploading, a
verification email is sent to every UID address.  The modal surfaces this
information so the user is not surprised when a freshly-uploaded key is
not immediately findable by email.

Modes
-----
    Search   Enter a fingerprint (40 hex / 0x-prefixed), key ID (16 hex /
             0x-prefixed), or email address.  On success the armored key
             is imported into the local keyring via gpg.import_keys().

    Upload   Uploads the public key for the cursor-selected key in the
             calling screen's KeyListWidget.  No passphrase required —
             only the public portion is sent.

Result dataclass
----------------
KeyserverResult
    mode          : "search" | "upload"
    query         : str   (search query or fingerprint of uploaded key)
    imported_fps  : list[str]  (fingerprints imported on search success)
    upload_ok     : bool
    cancelled     : bool
    error         : str   (human-readable error message, empty on success)
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
)


@dataclass
class KeyserverResult:
    mode: str
    query: str = ""
    imported_fps: list[str] = field(default_factory=list)
    upload_ok: bool = False
    cancelled: bool = False
    error: str = ""

    @classmethod
    def from_cancel(cls) -> "KeyserverResult":
        return cls(mode="search", cancelled=True)
    

_DEFAULT_TIMEOUT = 10


def _vks_fetch(base_url: str, query: str) -> tuple[str, str]:
    """
        Fetch an ASCII-armored public key from a VKS / Hagrid keyserver.

    Detects the query type and constructs the appropriate endpoint:
        40-hex or 0x+40-hex  → /vks/v1/by-fingerprint/<FP>
        16-hex or 0x+16-hex  → /vks/v1/by-keyid/<KEYID>
        contains @           → /vks/v1/by-email/<email>

    Returns (armored_key: str, error: str).
    On success error is ""; on failure armored_key is "".
    """
    q = query.strip()

    hex_q = q[2:] if q.lower().startswith("0x") else q

    if "@" in q:
        path = f"/vks/v1/by-email/{urllib.parse.quote(q, safe='')}"
    elif len(hex_q) == 40 and _is_hex(hex_q):
        path = f"/vk1/v1/by-fingerprint/{hex_q.upper()}"
    elif len(hex_q) == 16 and _is_hex(hex_q):
        path = f"vks/v1/by-keyid/{hex_q.upper()}"
    else:
        return (
            f"Unrecognized query format: '{q}'\n"
            "Use a full 40-char fingerprint, 16-char Key ID (prefix with 0x), "
            "or an email address."
        )
    
    url = base_url.rstrip("/") + path
    try:
        with urllib.request.urlopen(url, timeout=_DEFAULT_TIMEOUT) as resp:
            body = resp.read().decode("ascii", errors="replace")
        if "BEGIN PGP PUBLIC KEY BLOCK" not in body:
            return "", f"Server response did not contain a PGP key block.\nURL: {url}"
        return body, ""
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "", f"Key not found on server for query: {q}"
        return "", f"HTTP {exc.code} from {url}:\n{exc.reason}"
    except Exception as exc:
        return "", f"Unexpected error: {exc}"
    

def _vks_upload(base_url: str, armored_key: str) -> tuple[bool, str]:
    """
        Upload an ASCII-armored public key to a VKS keyserver.

    Returns (ok: bool, message: str).
    """
    url = base_url.rstrip("/") + "/vks/v1/upload"
    data = urllib.parse.urlencode({"keytext": armored_key}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return True, body
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = exc.reason
        return False, f"HTTP {exc.code}: {detail}"
    except urllib.error.URLError as exc:
        return False, f"Network error reaching {url}:\n{exc.reason}"
    except Exception as exc:
        return False, f"Unexpected error: {exc}"
    

def _is_hex(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False
    

class KeyserverModal(ModalScreen[KeyserverResult]):
    """
        Two-mode modal: Search (fetch + import) and Upload (publish).

    Parameters
    ----------
    gpg : gnupg.GPG
        The shared GPG instance — used to import fetched keys and to
        export the public key for upload.
    keyserver_url : str
        Base URL of the keyserver (e.g. "https://keys.openpgp.org").
    prefill_fingerprint : str | None
        If provided, the Upload tab is pre-selected and the fingerprint
        label is pre-populated.  Pass the cursor key's fingerprint when
        launching from KeyManagementScreen.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    def __init__(
        self,
        gpg,
        keyserver_url: str,
        prefill_fingerprint: str | None = None,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._gpg = gpg
        self._keyserver_url = keyserver_url
        self._prefill_fp = prefill_fingerprint
        self._mode = "upload" if prefill_fingerprint else "search"

    def compose(self) -> ComposeResult:
        with Container(id="ksm-outer"):
            with Vertical(id="ksm-inner"):
                yield Label("Keyserver", id="ksm-title")
                yield Static("-" * 46, id="ksm-divider")

                with Horizontal(classes="ksm-row"):
                    yield Label("Server", classes="ksm-label")
                    yield Static(
                        self._keyserver_url,
                        id="ksm-server-display",
                        classes="ksm-value"
                    )

                with RadioSet(id="ksm-mode-set"):
                    yield RadioButton(
                        "Search / Fetch",
                        value=(self._mode == "search"),
                        id="ksm-radio-search"
                    )
                    yield RadioButton(
                        "Upload / Publish",
                        value=(self._mode == "upload"),
                        id="ksm-radio-upload"
                    )

                with Container(id="ksm-search-pane"):
                    yield Label(
                        "Fingerprint, Key ID [i](0x...)[/i], or Email",
                        classes="ksm-field-label",
                        markup=True
                    )
                    yield Input(
                        placeholder="alice@example.com -or- 0xDEADBEEF...",
                        id="ksm-search-input"
                    )
                    yield Static("", id="ksm-search-hint", classes="ksm-hint")

                with Container(id="ksm-upload-pane"):
                    yield Label("Key to upload", classes="ksm-field-label")
                    yield Static(
                        self._prefill_fp or "(no key selected)",
                        id="ksm-upload-fp",
                        classes="ksm-value ksm-fp"
                    )
                    yield Static(
                        "Only the [b]public[/b] key is sent. "
                        "keys.openpgpg.org will email each UID address "
                        "a verification link before the key becomes "
                        "searchable by email.",
                        id="ksm-upload-note",
                        classes="ksm-note",
                        markup=True
                    )

                yield Static("", id="ksm-status", classes="ksm-status", markup=True)

                with Horizontal(id="ksm-buttons"):
                    yield Button("Go", variant="primary", id="ksm-btn-go")
                    yield Button("Cancel", variant="default", id="ksm-btn-cancel")
        
    def on_mount(self) -> None:
        self._apply_mode(self._mode)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        mode = "search" if event.radio_set.pressed_index == 0 else "upload"
        self._apply_mode(mode)

    def _apply_mode(self, mode: str) -> None:
        self._mode = mode
        search_pane = self.query_one("#ksm-search-pane", Container)
        upload_pane = self.query_one("#ksm-upload-pane", Container)
        go_btn = self.query_one("#ksm-btn-go", Button)

        if mode == "search":
            search_pane.display = True
            upload_pane.display = False
            go_btn.label = "Fetch & Import"
            self.query_one("#ksm-search-input", Input).focus()
        else:
            search_pane.display = False
            upload_pane.display = True
            go_btn.label = "Upload"
            fp = self._prefill_fp
            self.query_one("#ksm-upload-fp", Static).update(fp)
            go_btn.focus()
        
        self._set_status("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ksm-btn-go":
            self._run()
        elif event.button.id == "ksm-btn-cancel":
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "ksm-search-input" and not self._busy:
            self._run()

    def action_cancel(self) -> None:
        self.dismiss(KeyserverResult.from_cancel())

    def _run(self) -> None:
        if self._busy:
            return
        
        if self._mode == "search":
            query = self.query_one("#ksm-search-input", Input).value.strip()
            if not query:
                self._set_status("Enter a fingerprint, key ID, or email address.", err=True)
                return
            self._start_search(query)
        else:
            fp = self._prefill_fp
            if not fp:
                self._set_status("No key selected - close and select a key first.", err=True)
                return
            self._start_upload(fp)

    def _start_search(self, query: str) -> None:
        self._set_busy(True)
        self._set_status(f"Searching for: {query} ...")
        import asyncio
        self.run_worker(
            self._worker_search(query),
            thread=True,
            name="ksm_search"
        )

    async def _worker_search(self, query: str) -> None:
        import asyncio
        armored, err = await asyncio.to_thread(
            _vks_fetch, 
            self._keyserver_url,
            query
        )
        if err:
            self.app.call_from_thread(self._finish_search, query, None, err)
            return
        
        result = await asyncio.to_thread(self._gpg.import_keys, armored)
        fps: list[str] = getattr(result, "fingerprints", []) or []
        self.app.call_from_thread(self._finish_search, query, fps, "")

    def _finish_search(
        self,
        query: str,
        fps: list[str] | None,
        err: str
    ) -> None:
        self._set_busy(False)
        if err:
            self._set_status(f"✗  {err}", err=True)
            return
        
        if fps:
            detail = "  ".join(fp[-16:] for fp in fps)
            self._set_status(
                f"✔  Imported {len(fps)} key(s):\n {detail}"
            )
            self.dismiss(
                KeyserverResult(
                    mode="search",
                    query=query,
                    imported_fps=fps
                )
            )
        else:
            self._set_status(
                f"✔  Key fetched - already in keyring (no new imports)."
            )
            self.dismiss(
                KeyserverResult(
                    mode="search",
                    query=query,
                    imported_fps=[]
                )
            )

    def _start_upload(self, fingerprint: str) -> None:
        try:
            armored = self._gpg.export_keys(fingerprint, armor=True)
        except Exception as exc:
            self._set_status(f"✗  Could not export key: {exc}", err=True)
            return
        
        if not armored:
            self._set_status(
                "✗  No public key data found for this fingerprint.", err=True
            )
            return
        
        self._set_busy(True)
        self._set_status(f"Uploading {fingerprint[-16:]} ...")
        self.run_worker(
            self._worker_upload(fingerprint, armored),
            thread=True,
            name="ksm_upload"
        )

    async def _worker_upload(self, fingerprint: str, armored: str) -> None:
        import asyncio
        ok, msg = await asyncio.to_thread(
            _vks_upload,
            self._keyserver_url,
            armored
        )
        self.app.call_from_thread(self._finish_upload, fingerprint, ok, msg)

    def _finish_upload(self, fingerprint: str, ok: bool, msg: str) -> None:
        self._set_busy(False)
        if ok:
            self._set_status(
                f"✔  Key {fingerprint[-16:]} uploaded.\n"
                "Check your email to verify each UID address "
                "(required before the key is searchable by email)."
            )
            self.dismiss(
                KeyserverResult(
                    mode="upload",
                    query=fingerprint,
                    upload_ok=True
                )
            )
        else:
            self._set_status(f"✗  Upload failed:\n{msg}", err=True)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy

    def _set_status(self, text: str, *, err: bool = False) -> None:
        status = self.query_one("#ksm-status", Static)
        status.update(text)
        if err:
            status.remove_class("ksm-status-ok")
            status.add_class("ksm-status-err")
        else:
            status.remove_class("ksm-status-err")
            status.add_class("ksm-status-ok")
