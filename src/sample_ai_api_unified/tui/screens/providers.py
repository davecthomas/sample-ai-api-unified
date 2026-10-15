"""Providers & configuration screen: engine/model status and API-key setup."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Static

from ... import catalog, envfile, fallback, onboarding, state
from ..modals import ChoiceModal, OnboardingModal
from .base import CapabilityScreen

# Completions retry policy (library 2.15): "default" keeps each engine's built-in
# retries; "none" collapses to a single attempt. Read by the factory via the
# COMPLETIONS_RETRY_POLICY environment variable.
RETRY_POLICY_ENV = "COMPLETIONS_RETRY_POLICY"
RETRY_POLICIES = ("default", "none")


class ProvidersScreen(CapabilityScreen):
    title_text = "Providers & models"
    subtitle_text = "Switch engines and models, and configure provider credentials."

    def compose_body(self) -> ComposeResult:
        yield Static("Capabilities", classes="field-label")
        yield DataTable(id="config-table", cursor_type="none")
        yield Static("Provider credentials", classes="field-label")
        yield DataTable(id="status-table", cursor_type="none")
        yield Static("", classes="field-label", id="retry-line")
        yield Static("", classes="field-label", id="fallback-line")
        with Horizontal(classes="actions"):
            yield Button("Switch engine…", variant="primary", id="switch")
            yield Button("Configure keys…", id="keys")
            yield Button("Retry policy…", id="retry")
            yield Button("Fallback chain…", id="fallback")

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
        policy = envfile.get_env(RETRY_POLICY_ENV, "") or "default"
        self.query_one("#retry-line", Static).update(
            f"completions retry policy: {policy}  ({RETRY_POLICY_ENV})"
        )
        chain = fallback.current_chain()
        self.query_one("#fallback-line", Static).update(
            f"completions fallback chain: {chain} on {fallback.current_fallback_on()}  "
            f"({fallback.FALLBACKS_ENV})"
            if chain
            else f"completions fallback chain: off  ({fallback.FALLBACKS_ENV})"
        )

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

    @on(Button.Pressed, "#retry")
    def _on_retry(self) -> None:
        current = envfile.get_env(RETRY_POLICY_ENV, "") or "default"
        options = [
            (f"{policy}{' (current)' if policy == current else ''}", policy)
            for policy in RETRY_POLICIES
        ]

        def picked(policy: str | None) -> None:
            if not policy:
                return
            envfile.set_env_values({RETRY_POLICY_ENV: policy})
            self.set_result(
                "result",
                f"Completions retry policy set to {policy!r} "
                f"({RETRY_POLICY_ENV}). 'none' collapses each engine to a single attempt; "
                "'default' keeps its built-in retries.",
            )
            self._refresh()

        self.app.push_screen(ChoiceModal("Completions retry policy", options), picked)

    @on(Button.Pressed, "#fallback")
    def _on_fallback(self) -> None:
        # Model fallback (library 2.32): COMPLETIONS_FALLBACKS turns every
        # factory-built completions client into an AiFallbackCompletions.
        current = fallback.current_chain()
        current_on = fallback.current_fallback_on()
        choices = [
            (
                f"Gemini ({fallback.GEMINI_FALLBACK}) on outages, rate limits, quota, rejected keys",
                fallback.DEFAULT_FALLBACK_ON,
            ),
            (
                f"Gemini ({fallback.GEMINI_FALLBACK}), also on unknown/retired models",
                fallback.FALLBACK_ON_WITH_MODEL,
            ),
            ("Off", ""),
        ]
        options = []
        for label, fallback_on in choices:
            is_current = (
                current == fallback.GEMINI_FALLBACK
                and fallback.same_reasons(current_on, fallback_on)
                if fallback_on
                else not current
            )
            options.append((f"{label}{' (current)' if is_current else ''}", fallback_on or "off"))

        def picked(choice: str | None) -> None:
            if not choice:
                return
            if choice == "off":
                fallback.clear_chain()
                self.set_result("result", "Completions fallback chain turned off.")
                self._refresh()
                return
            google = catalog.PROVIDERS["google"]
            if not catalog.provider_configured(google):
                # The fallback engine needs its own credentials, exactly as it
                # would as the primary; collect them before saving the chain.
                def done(ready: bool) -> None:
                    if ready:
                        self._save_fallback(choice)
                    else:
                        self.set_result(
                            "result",
                            "[yellow]Google Gemini not configured; fallback chain "
                            "not saved.[/yellow]",
                        )

                self.app.push_screen(OnboardingModal(google), done)
                return
            self._save_fallback(choice)

        self.app.push_screen(ChoiceModal("Completions fallback chain", options), picked)

    def _save_fallback(self, fallback_on: str) -> None:
        fallback.set_chain(fallback.GEMINI_FALLBACK, fallback_on)
        reasons = (
            f"{fallback.FALLBACK_ON_ENV} unset, so the library default applies ({fallback_on})"
            if fallback.same_reasons(fallback_on, fallback.DEFAULT_FALLBACK_ON)
            else f"{fallback.FALLBACK_ON_ENV}={fallback_on}"
        )
        self.set_result(
            "result",
            f"Fallback chain set: {fallback.FALLBACKS_ENV}={fallback.GEMINI_FALLBACK}, "
            f"{reasons}. A completions request that fails with one of those reasons is "
            "retried on Gemini; results name the fallback when it answered.",
        )
        self._refresh()

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
