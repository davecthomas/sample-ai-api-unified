"""Copy text to the system clipboard (best-effort, cross-platform).

The Textual app's own ``copy_to_clipboard`` emits an OSC 52 terminal escape,
which many terminals (including macOS Terminal.app) ignore, so nothing reaches
the real clipboard. Shelling out to the OS clipboard tool puts the text where
the user can paste it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def _clipboard_command() -> list[str] | None:
    """The command that reads stdin and writes it to the OS clipboard, if any."""
    if sys.platform == "darwin" and shutil.which("pbcopy"):
        return ["pbcopy"]
    if sys.platform == "win32":
        return ["clip"]
    if shutil.which("wl-copy"):
        return ["wl-copy"]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard"]
    if shutil.which("xsel"):
        return ["xsel", "--clipboard", "--input"]
    return None


def copy_to_clipboard(text: str) -> bool:
    """Write ``text`` to the OS clipboard. Return True on success."""
    command = _clipboard_command()
    if command is None:
        return False
    try:
        subprocess.run(command, input=text.encode("utf-8"), check=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return True
