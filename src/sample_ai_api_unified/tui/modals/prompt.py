"""A modal that collects one line (or block) of text, or None if cancelled."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class PromptModal(ModalScreen[str | None]):
    """Return the entered text on submit, or None on cancel."""

    def __init__(self, title: str, *, default: str = "", password: bool = False) -> None:
        super().__init__()
        self._title = title
        self._default = default
        self._password = password

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._title, id="dialog-title")
            yield Input(value=self._default, password=self._password, id="prompt-input")
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("OK", variant="primary", id="ok")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    @on(Input.Submitted)
    def _submit(self) -> None:
        self.dismiss(self.query_one("#prompt-input", Input).value)

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self.dismiss(self.query_one("#prompt-input", Input).value)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)
