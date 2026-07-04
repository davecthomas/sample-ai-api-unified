"""A modal listing options; returns the chosen value or None if cancelled."""

from __future__ import annotations

from typing import Any, Sequence

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView


class ChoiceModal(ModalScreen[Any]):
    """Options are (label, value) pairs. Dismisses with the chosen value."""

    def __init__(self, title: str, options: Sequence[tuple[str, Any]]) -> None:
        super().__init__()
        self._title = title
        self._options = list(options)

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._title, id="dialog-title")
            items = [ListItem(Label(label)) for label, _ in self._options]
            yield ListView(*items, id="choice-list")
            yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#choice-list", ListView).focus()

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is not None and 0 <= index < len(self._options):
            self.dismiss(self._options[index][1])

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)
