"""Screen shown for capabilities whose Textual UI is not built yet.

These capabilities work today in the classic Rich app (``make run-classic``);
their Textual screens land in a follow-up PR.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static

from .base import CapabilityScreen


class PlaceholderScreen(CapabilityScreen):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.title_text = label
        self.subtitle_text = "Not yet available in the TUI."

    def compose_body(self) -> ComposeResult:
        yield Static(
            "This capability's Textual screen is coming in a follow-up PR.\n\n"
            "It is fully available now in the classic menu app:\n\n"
            "    make run-classic",
            classes="result-panel",
        )
