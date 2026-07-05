"""Providers & configuration screen: engine/model status and API-key setup."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Static

from ... import catalog, onboarding, state
from ..modals import ChoiceModal, OnboardingModal
from .base import CapabilityScreen


class ProvidersScreen(CapabilityScreen):
    title_text = "Providers & models"
    subtitle_text = "Switch engines and models, and configure provider credentials."

    def compose_body(self) -> ComposeResult:
        yield Static("Capabilities", classes="field-label")
        yield DataTable(id="config-table", cursor_type="none")
        yield Static("Provider credentials", classes="field-label")
        yield DataTable(id="status-table", cursor_type="none")
        with Horizontal(classes="actions"):
            yield Button("Switch engine…", variant="primary", id="switch")
            yield Button("Configure keys…", id="keys")

    def on_mount(self) -> None:
        config = self.query_one("#config-table", DataTable)
        config.add_columns("Capability", "Engine", "Model")
        status = self.query_one("#status-table", DataTable)
        status.add_columns("Provider", "Status", "Detail")
        self._refresh()

    def _refresh(self) -> None:
        config = self.query_one("#config-table", DataTable)
        config.clear()
        for key, capability in catalog.CAPABILITIES.items():
            config.add_row(
                capability.label,
                state.current_engine(key) or "unset",
                state.current_model(key) or "provider default",
            )
        status = self.query_one("#status-table", DataTable)
        status.clear()
        for label, state_text, detail in onboarding.provider_status_rows():
            plain_status = state_text.replace("[green]", "").replace("[/green]", "")
            plain_status = plain_status.replace("[red]", "").replace("[/red]", "")
            status.add_row(label, plain_status, detail)

    @on(Button.Pressed, "#switch")
    def _on_switch(self) -> None:
        options = [(cap.label, key) for key, cap in catalog.CAPABILITIES.items()]

        def picked_capability(capability_key: str | None) -> None:
            if capability_key:
                self._switch_engine(capability_key)

        self.app.push_screen(ChoiceModal("Switch which capability?", options), picked_capability)

    def _switch_engine(self, capability_key: str) -> None:
        capability = catalog.CAPABILITIES[capability_key]
        options = [
            (f"{e.selector} ({catalog.PROVIDERS[e.provider].label})", e.selector)
            for e in capability.engines
        ]

        def picked_engine(selector: str | None) -> None:
            if not selector:
                return
            provider = catalog.provider_for_engine(capability_key, selector)
            if provider and not catalog.provider_configured(provider):
                self._onboard_then_set(provider, capability_key, selector)
            else:
                state.set_engine(capability_key, selector)
                self.set_result("result", f"{capability.label} engine set to {selector}")
                self._refresh()

        self.app.push_screen(
            ChoiceModal(f"{capability.label}: choose engine", options), picked_engine
        )

    def _onboard_then_set(self, provider, capability_key, selector) -> None:
        def done(ready: bool) -> None:
            if ready:
                state.set_engine(capability_key, selector)
                self.set_result("result", f"Engine set to {selector}")
                self._refresh()
            else:
                self.set_result("result", f"[yellow]{provider.label} not configured.[/yellow]")

        self.app.push_screen(OnboardingModal(provider), done)

    @on(Button.Pressed, "#keys")
    def _on_keys(self) -> None:
        options = [(p.label, p.key) for p in catalog.PROVIDERS.values()]

        def picked(provider_key: str | None) -> None:
            if not provider_key:
                return
            provider = catalog.PROVIDERS[provider_key]

            def done(ready: bool) -> None:
                self.set_result(
                    "result",
                    f"{provider.label} {'configured' if ready else 'still needs keys'}.",
                )
                self._refresh()

            self.app.push_screen(OnboardingModal(provider), done)

        self.app.push_screen(ChoiceModal("Configure which provider?", options), picked)
