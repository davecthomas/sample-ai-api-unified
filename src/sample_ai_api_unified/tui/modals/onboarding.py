"""Modal that collects a provider's missing credentials and saves them to .env.

One input per required env key, honoring Google's service-account mode via
catalog.required_env_keys. Dismisses True when the provider becomes ready.
"""

from __future__ import annotations

import webbrowser

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from ... import catalog, envfile


class OnboardingModal(ModalScreen[bool]):
    def __init__(self, provider: catalog.Provider) -> None:
        super().__init__()
        self._provider = provider
        self._keys = list(catalog.required_env_keys(provider))

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Configure {self._provider.label}", id="dialog-title")
            yield Label(f"Get credentials: {self._provider.key_url}", id="dialog-message")
            with VerticalScroll():
                for key in self._keys:
                    suffix = " (optional)" if key.optional else ""
                    yield Label(f"{key.name}{suffix}", classes="field-label")
                    yield Input(
                        value=key.default if key.optional else "",
                        password=key.secret,
                        id=f"key-{key.name}",
                    )
            with Horizontal(id="dialog-buttons"):
                yield Button("Open key page", id="open-url")
                yield Button("Cancel", id="cancel")
                yield Button("Save", variant="primary", id="save")

    @on(Button.Pressed, "#open-url")
    def _open_url(self) -> None:
        webbrowser.open(self._provider.key_url)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#save")
    def _save(self) -> None:
        values: dict[str, str] = {}
        for key in self._keys:
            entered = self.query_one(f"#key-{key.name}", Input).value.strip()
            if entered:
                values[key.name] = entered
            elif not key.optional:
                self.query_one("#dialog-message", Label).update(f"{key.name} is required.")
                return
        envfile.set_env_values(values)
        envfile.reload_env()
        self.dismiss(catalog.provider_configured(self._provider))
