"""A yes/no modal returning a bool. Used for cost/time confirmations."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmModal(ModalScreen[bool]):
    def __init__(self, message: str, *, default: bool = True) -> None:
        super().__init__()
        self._message = message
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Confirm", id="dialog-title")
            yield Label(self._message, id="dialog-message")
            with Horizontal(id="dialog-buttons"):
                yield Button("No", variant="default", id="no")
                yield Button("Yes", variant="primary", id="yes")

    def on_mount(self) -> None:
        self.query_one("#yes" if self._default else "#no", Button).focus()

    @on(Button.Pressed, "#yes")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def _no(self) -> None:
        self.dismiss(False)
