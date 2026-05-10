"""
app.py
------
Entry point for the Partizan Guard GPG Interface.

"""

import argparse
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

try:
    from partizan_gpg.cipherlib import build_gpg
except ImportError as exc:
    print(
        f"[FATAL] Cannot import `cipherlib`: {exc}\n"
        "Ensure the `cipherlib/` package is in the parent of this file's directory."
    )
    sys.exit(1)

from partizan_gpg.tui.settings import AppSettings, load_settings, save_settings


_CSS_DIR = Path(__file__).parent / "css"


def _import_key_management_screen():
    from partizan_gpg.tui.screens.key_management import KeyManagementScreen
    return KeyManagementScreen


def _import_encrypt_decrypt_screen():
    from partizan_gpg.tui.screens.encrypt_decrypt import EncryptDecryptScreen
    return EncryptDecryptScreen


def _import_config_screen():
    from partizan_gpg.tui.screens.config_settings import ConfigScreen
    return ConfigScreen


class PlaceholderScreen(Screen):

    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]

    def __init__(self, title: str = "Coming soon", **kwargs):
        super().__init__(**kwargs)
        self._title = title
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(
            f"\n  [ {self._title} ]\n\n  This screen is not yet implemented.\n  Press [b]Q[/b] or [b]Escape[/b] to go back.",
            markup=True,
            id="placeholder-label"
        )
        yield Footer()


class GPGApp(App):

    TITLE = "Partizan Guard GPG"
    SUB_TITLE = "GnuPG key management & crypto operations"
    STYLE_DIR = _CSS_DIR

    CSS = """
    #passphrase-modal-outer {
        align: center middle;
        width: 100%;
        height: 100%;
    }
    #passphrase-modal-inner {
        width: 62;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }
    #passphrase-modal-title {
        text-stye: bold;
        color: $text;
        width: 100%;
        margin-bottom: 0;
        overflow: hidden;
    }
    #passphrase-modal-divider {
        color: $primary;
        margin-bottom: 1;
    }
    #passphrase-field-label {
        color: $text-muted;
        margin-bottom: 0;
    }
    #passphrase-input {
        width: 100%;
        margin-bottom: 1;
        border: tall $primary-darken-1;
    }
    #passphrase-input:focus {
        border: tall $primary;
    }
    #passphrase-modal-buttons {
        layout: horizontal;
        height: auto;
        align: right middle;
        width: 100%;
    }
    #passphrase-modal-buttons Button {
        margin-left: 1;
        min-width: 10;
    }
    
    Screen {
        background: $background;
    }
    
    Header {
        background: $primary;
        color: $text;
        height: 1;
        dock: top;
    }
    
    Footer {
        background: $primary-darken-2;
        color: $text-muted;
        height: 1;
        dock: bottom;
    }
    
    #welcome-label {
        padding: 1 4;
        color: $text;
        content-align: left top;
    }
    #placeholder-label {
        padding: 2 4;
        color: $text-muted;
        content-align: left top;
    }
    """

    BINDINGS = [
        Binding("k", "switch_screen('keys')", "Keys"),
        Binding("e", "switch_screen('encrypt')", "Encrypt/Decrypt"),
        Binding("s", "switch_screen('config')", "Settings Config", priority=True),
        Binding("escape", "quit", "Quit", priority=True),
    ]

    def __init__(self, gpg_instance, settings: AppSettings, **kwargs):
        super().__init__(**kwargs)
        self.gpg = gpg_instance
        self.settings = settings

    def on_mount(self) -> None:
        self.install_screen(self._make_key_screen, name="keys")
        self.install_screen(self._make_encrypt_screen, name="encrypt")
        self.install_screen(self._make_config_screen, name="config")

    def _make_key_screen(self):
        try:
            KeyManagementScreen = _import_key_management_screen()
            return KeyManagementScreen(self.gpg)
        except (ImportError, ModuleNotFoundError):
            return PlaceholderScreen("Key Management  (not yet implemented)")
        
    def _make_encrypt_screen(self):
        try:
            EncryptDecryptScreen = _import_encrypt_decrypt_screen()
            return EncryptDecryptScreen(self.gpg)
        except (ImportError, ModuleNotFoundError):
            return PlaceholderScreen("Encrypt / Decrypt  (not yet implemented)")
        
    def _make_config_screen(self):
        try:
            ConfigScreen = _import_config_screen()
            return ConfigScreen(self.settings)
        except (ImportError, ModuleNotFoundError):
            return PlaceholderScreen("Settings Config  (not yet implemented)")
        
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(WELCOME_TEXT, id="welcome-label", markup=True)
        yield Footer()

    _TOP_LEVEL_SCREENS = frozenset({
        "KeyManagementScreen",
        "EncryptDecryptScreen",
        "ConfigScreen",
    })

    def action_switch_screen(self, screen_name: str) -> None:
        if self.screen.__class__.__name__ in self._TOP_LEVEL_SCREENS:
            return
        self.push_screen(screen_name)

    def on_config_screen_saved(
        self,
        message: "ConfigScreen.Saved" # type: ignore[name-defined]
    ) -> None:
        new_cfg = message.settings
        self.settings = new_cfg

        try:
            new_gpg = new_cfg.build_gpg()
        except RuntimeError as exc:
            self.notify(
                f"Settings saved, but GPG could not be reloaded:\n{exc}\n\n"
                "The previous keyring is still active.",
                title="GPG reload failed",
                severity="warning",
                timeout=10
            )
            return
        
        self.gpg = new_gpg
        self.SUB_TITLE = f"keyring: {new_gpg.gnupghome}"

        self._propagate_gpg_to_screens(new_gpg)

        self.notify(
            f"Keyring: {new_gpg.gnupghome}",
            title="Settings saved",
            severity="information",
            timeout=4
        )
    
    def _propagate_gpg_to_screens(self, gpg) -> None:
        for name in ("keys", "encrypt"):
            try:
                screen = self._installed_screens.get(name)
                if screen is None:
                    continue

                if callable(screen):
                    continue
                if hasattr(screen, "gpg"):
                    screen.gpg = gpg
                
                try:
                    from partizan_gpg.tui.widgets.key_list import KeyListWidget
                    for widget in screen.query(KeyListWidget):
                        widget.refresh_keys(gpg)
                except Exception:
                    pass
            except Exception:
                pass


WELCOME_TEXT = """\

  ██████╗ ██████╗  ██████╗
 ██╔════╝ ██╔══██╗██╔════╝
 ██║  ███╗██████╔╝██║  ███╗
 ██║   ██║██╔═══╝ ██║   ██║
 ╚██████╔╝██║     ╚██████╔╝
  ╚═════╝ ╚═╝      ╚═════╝   TUI

[i]GnuPG key management & cryptographic operations.[/i]

[b][u]Navigation[/u][/b]

[b]K[/b]    →   Key Management    [i](generate, import, export, delete keys)[/i]
[b]E[/b]    →   Encrypt / Decrypt [i](encrypt, decrypt, sign, verify)[/i]
[b]S[/b]    →   Settings          [i](keyring path, GPG binary, key defaults)[/i]
[b]Esc[/b]    →   Quit

The keyring path is shown in the header subtitle.
[i]Use [b]`--gnupghome`[/b] on the command line to point at a different keyring.[/i]
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Partizan Guard GPG - GnuPG key management & crypto operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--gnupghome",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to the GNUPGHOME keyring directory. "
            "Overrides the stored setting for this session. "
            "Defaults to the value saved in settings, orthe built-in test keyring."
        )
    )
    parser.add_argument(
        "--gpg-binary",
        type=str,
        default=None,
        metavar="BINARY",
        help=(
            "Name or full path of the gpg binary. "
            "Overrides the stored setting for this session."
        )
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cfg = load_settings()

    if args.gnupghome is not None:
        cfg.gnupghome = str(args.gnupghome)
    if args.gpg_binary is not None:
        cfg.gpg_binary = args.gpg_binary

    try:
        gpg = cfg.build_gpg()
    except RuntimeError as exc:
        print(f"[FATAL] Failed to initialize GPG: {exc}")
        sys.exit(1)
    
    app = GPGApp(gpg_instance=gpg, settings=cfg)
    app.SUB_TITLE = f"keyring: {gpg.gnupghome}"

    app.run()


if __name__ == "__main__":
    main()



# """
# app.py
# ------
# Entry point for the Partizan Guard GPG Interface.

# Responsibilities:
#     - Parse CLI arguments (`--gnupghome`, `--gpg-binary`)
#     - Instantiate the shared `gnupg.GPG` object via `build_gpg()`
#     - Register and mount all screens
#     - Provide app-level key bindings for screen navigation
#     - Expose the shared gpg instance to all screens via `App.gpg`
    
# Usage:
#     `python app.py`
#     `python app.py --gnupghome ~/.gnupg`
#     `python app.py --gnupghome ~/.gnupg --gpg-binary gpg2`
    
# Screens:
#     K -> KeyManagementScreen
#     E -> EncryptDecryptScreen
#     Q -> Quit
# """

# import argparse
# import sys
# from pathlib import Path

# from textual.app import App, ComposeResult
# from textual.binding import Binding
# from textual.widgets import Footer, Header, Label
# from textual.screen import Screen

# try:
#     # from py_partizan.cipherlib import build_gpg
#     from partizan_gpg.cipherlib import build_gpg
# except ImportError as exc:
#     print(
#         f"[FATAL] Cannot import `cipherlib`: {exc}\n"
#         "Ensure the `cipherlib/` package is in the same directory as `app.py`\n"
#         "and that 'python-gnupg' is installed:  `pip install python-gnupg textual`"
#     )
#     sys.exit(1)


# _CSS_DIR = Path(__file__).parent / "css"


# def _import_key_management_screen():
#     from partizan_gpg.tui.screens.key_management import KeyManagementScreen
#     return KeyManagementScreen


# def _import_encrypt_decrypt_screen():
#     from partizan_gpg.tui.screens.encrypt_decrypt import EncryptDecryptScreen
#     return EncryptDecryptScreen


# class PlaceholderScreen(Screen):
#     """Generic placeholder for screens not yet implemented."""

#     BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]

#     def __init__(self, title: str = "Coming soon", **kwargs):
#         super().__init__(**kwargs)
#         self._title = title

#     def compose(self) -> ComposeResult:
#         yield Header()
#         yield Label(
#             f"\n  [ {self._title} ]\n\n  This screen is not yet implemented.\n  Press Q or Escape to go back.",
#             id="placeholder-label"
#         )
#         yield Footer()


# class GPGApp(App):
#     """
#     Root application class.
    
#     Attributes
#     ----------
#     gpg : gnupg.GPG
#         The shared GPG instance. Screens and widgets should access this via
#         `self.app.gpg` - never construct their own GPG instance.
#     """

#     TITLE = "Partizan Guard GPG" 
#     SUB_TITLE = "GnuPG key management & crypto operations"

#     CSS_PATH = str(_CSS_DIR / "app.tcss")

#     BINDINGS = [
#         Binding("k", "switch_screen('keys')", "Keys", priority=True),
#         Binding("e", "switch_screen('encrypt')", "Encrypt/Decrypt", priority=True),
#         Binding("q", "quit", "Quit", priority=True),
#     ]

#     def __init__(self, gpg_instance, **kwargs):
#         """
#         Parameters
#         ----------
#         gpg_instance : gnupg.GPG
#             Pre-built GPG instance from `build_gpg()`. Stored as `self.gpg` and
#             shared with all screens.
#         """
#         super().__init__(**kwargs)
#         self.gpg = gpg_instance

#     def on_mount(self) -> None:
#         """
#         Register named screens on mount rather than via `SCREENS` class var
#         so we can pass `self` (and therefore `self.gpg`) to each screen
#         constructor when the user first navigates to them.
        
#         Named screens are installed with `install_screen()`; they are
#         instantiated lazily on first `switch_screen()`; they are 
#         instantiated lazily on first `switch_screen()` call.
#         """
#         self.install_screen(self._make_key_screen, name="keys")
#         self.install_screen(self._make_encrypt_screen, name="encrypt")
    
#     def _make_key_screen(self):
#         try:
#             KeyManagementScreen = _import_key_management_screen()
#             return KeyManagementScreen(self.gpg)
#         except (ImportError, ModuleNotFoundError):
#             return PlaceholderScreen("Key Management  (not yet implemented)")
        
#     def _make_encrypt_screen(self):
#         try:
#             EncryptDecryptScreen = _import_encrypt_decrypt_screen()
#             return EncryptDecryptScreen(self.gpg)
#         except (ImportError, ModuleNotFoundError):
#             return PlaceholderScreen("Encrypt / Decrypt (not yet implemented)")

#     def compose(self) -> ComposeResult:
#         """
#         The home view is intentionally minimal: just the header, a welcome
#         label, and the footer with key bindings. All real work happens
#         inside the named screens.
#         """
#         yield Header()
#         yield Label(WELCOME_TEXT, id="welcome-label", markup=True)
#         yield Footer()

#     def action_switch_screen(self, screen_name: str) -> None:
#         """
#         Navigate to a named screen. Uses `switch_screen()` so the home view
#         is replaced rather than stacked (no Escape-to-go-back required for
#         top-level navigation).
#         """
#         if self.screen.__class__.__name__ in (
#             "KeyManagementScreen",
#             "EncryptDecryptScreen"
#         ):
#             return
#         self.push_screen(screen_name)


# WELCOME_TEXT = """\

#   ██████╗ ██████╗  ██████╗
#  ██╔════╝ ██╔══██╗██╔════╝
#  ██║  ███╗██████╔╝██║  ███╗
#  ██║   ██║██╔═══╝ ██║   ██║
#  ╚██████╔╝██║     ╚██████╔╝
#   ╚═════╝ ╚═╝      ╚═════╝   TUI

# [i]GnuPG key management & cryptographic operations.[/i]

# [b][u]Navigation[/u][/b]

# [b]K[/b]    →   Key Management    [i](generate, import, export, delete keys)[/i]
# [b]E[/b]    →   Encrypt / Decrypt [i](encrypt, decrypt, sign, verify)[/i]
# [b]Q[/b]    →   Quit

# The keyring path is shown in the header subtitle.
# [i]Use [b]`--gnupghome`[/b] on the command line to point at a different keyring.[/i]
# """

# def parse_args() -> argparse.Namespace:
#     parser = argparse.ArgumentParser(
#         description="Partizan Guard GPG - GnuPG key management & crypto operations",
#         formatter_class=argparse.RawDescriptionHelpFormatter,
#         epilog=__doc__
#     )
#     parser.add_argument(
#         "--gnupghome",
#         type=Path,
#         default=None,
#         metavar="PATH",
#         help=(
#             "Path to the GNUPGHOME keyring directory. "
#             "Defaults to `../cipherlib/test_keyring/` (the isolated test keyring). "
#             "Pass `~/.gnupg` to use your real system keyring."
#         )
#     )
#     parser.add_argument(
#         "--gpg-binary",
#         type=str,
#         default="gpg",
#         metavar="BINARY",
#         help="Name or full path of the gpg binary (default: `gpg`)."
#     )
#     return parser.parse_args()


# def main() -> None:
#     args = parse_args()

#     try:
#         gpg = build_gpg(gnupghome=args.gnupghome, binary=args.gpg_binary)
#     except RuntimeError as exc:
#         print(f"[FATAL] Failed to initialize GPG: {exc}")
#         sys.exit(1)

#     app = GPGApp(gpg_instance=gpg)
#     app.SUB_TITLE = f"keyring: {gpg.gnupghome}"
    
#     app.run()


# if __name__ == "__main__":
#     main()