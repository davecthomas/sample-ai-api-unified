"""Middleware screen: a form-based profile editor plus PII and observability demos.

The form maps to middleware_profile dataclasses and writes the YAML the library
expects (AI_MIDDLEWARE_CONFIG_PATH); the user never edits YAML directly.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label, Select, Static, Switch

from ... import middleware_profile as mp
from ... import obs, samples, state
from .base import CapabilityScreen

CAPABILITY = "completions"


def _select(options: tuple[str, ...], value: str, widget_id: str) -> Select:
    return Select([(opt, opt) for opt in options], value=value, allow_blank=False, id=widget_id)


class MiddlewareScreen(CapabilityScreen):
    title_text = "Middleware"
    subtitle_text = "Edit the observability + PII profile, then run the demos."

    def compose_body(self) -> ComposeResult:
        profile = mp.read_profile()

        yield Label("Observability", classes="field-label")
        with Horizontal(classes="form-row"):
            yield Label("enabled")
            yield Switch(value=profile.observability.enabled, id="obs-enabled")
            yield Label("direction")
            yield _select(mp.DIRECTIONS, profile.observability.direction, "obs-direction")
            yield Label("log level")
            yield _select(mp.LOG_LEVELS, profile.observability.log_level, "obs-log-level")

        yield Label("PII redaction", classes="field-label")
        with Horizontal(classes="form-row"):
            yield Label("enabled")
            yield Switch(value=profile.pii.enabled, id="pii-enabled")
            yield Label("strict")
            yield Switch(value=profile.pii.strict_mode, id="pii-strict")
        with Horizontal(classes="form-row"):
            yield Label("direction")
            yield _select(mp.DIRECTIONS, profile.pii.direction, "pii-direction")
            yield Label("profile")
            yield _select(mp.DETECTION_PROFILES, profile.pii.detection_profile, "pii-profile")

        with Horizontal(classes="actions"):
            yield Button("Save profile", variant="primary", id="save")
            yield Button("PII demo", id="pii-demo")
            yield Button("Observability demo", id="obs-demo")
        yield Static("", classes="result-panel", id="result")

    @on(Button.Pressed, "#save")
    def _on_save(self) -> None:
        profile = mp.MiddlewareProfile(
            observability=mp.ObservabilityProfile(
                enabled=self.query_one("#obs-enabled", Switch).value,
                direction=self.query_one("#obs-direction", Select).value,
                log_level=self.query_one("#obs-log-level", Select).value,
            ),
            pii=mp.PiiProfile(
                enabled=self.query_one("#pii-enabled", Switch).value,
                strict_mode=self.query_one("#pii-strict", Switch).value,
                direction=self.query_one("#pii-direction", Select).value,
                detection_profile=self.query_one("#pii-profile", Select).value,
            ),
        )
        path = mp.write_profile(profile)
        self.set_result("result", f"Profile written to {path}\nand AI_MIDDLEWARE_CONFIG_PATH set.")

    @on(Button.Pressed, "#pii-demo")
    def _on_pii_demo(self) -> None:
        # Ensure PII is enabled so the config the redactor reads is active.
        profile = mp.read_profile()
        if not profile.pii.enabled:
            from dataclasses import replace

            mp.write_profile(replace(profile, pii=replace(profile.pii, enabled=True)))
            self.query_one("#pii-enabled", Switch).value = True

        def call() -> str:
            from ai_api_unified.middleware.pii_redactor import AiApiPiiMiddleware

            redactor = AiApiPiiMiddleware()
            lines = ["PII redaction (all PII is fabricated):", ""]
            for sample in samples.PII_SAMPLES:
                lines.append(f"in : {sample}")
                lines.append(f"out: {redactor.process_input(sample)}")
                lines.append("")
            return "\n".join(lines)

        self.run_blocking(
            call, on_success=lambda text: self.set_result("result", text), description="Redacting"
        )

    @on(Button.Pressed, "#obs-demo")
    def _on_obs_demo(self) -> None:
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Completions engine not configured.[/yellow]")
            return
        # Make sure observability is on so the call emits events.
        profile = mp.read_profile()
        if not profile.observability.enabled:
            mp.write_profile(profile)
            self.query_one("#obs-enabled", Switch).value = True

        def call() -> str:
            from ai_api_unified import AIFactory
            from ai_api_unified.middleware import set_observability_context

            set_observability_context(
                caller_id="sample-app", session_id="tui", workflow_id="observability-demo"
            )
            obs.clear()
            client = AIFactory.get_ai_completions_client()
            reply = client.send_prompt("Reply with the single word: observed")
            events = obs.all_events()
            return (
                f"Model replied: {reply.strip()}\n\n"
                f"Captured {len(events)} observability events (metadata only). "
                "See the docked pane below."
            )

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Observed completion via {state.current_engine(CAPABILITY)}",
        )
