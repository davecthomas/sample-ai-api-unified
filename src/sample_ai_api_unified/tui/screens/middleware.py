"""Middleware screen: a form-based profile editor plus PII and observability demos.

The form maps to middleware_profile dataclasses and writes the YAML the library
expects (AI_MIDDLEWARE_CONFIG_PATH); the user never edits YAML directly.
"""

from __future__ import annotations

from dataclasses import replace

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label, Select, Switch

from ... import middleware_profile as mp
from ... import obs, samples, state
from .base import CapabilityScreen

CAPABILITY = "completions"


def _select(options: tuple[str, ...], value: str, widget_id: str) -> Select:
    # Fall back to the first option if a persisted value is not a valid choice,
    # so a hand-edited YAML cannot crash the screen at mount.
    safe = value if value in options else options[0]
    return Select([(opt, opt) for opt in options], value=safe, allow_blank=False, id=widget_id)


class MiddlewareScreen(CapabilityScreen):
    title_text = "Middleware"
    subtitle_text = "Changes apply immediately. Run the demos below."

    # Widgets fire Changed events during initial mount; only persist real user
    # edits, enabled once after the first refresh.
    _autosave = False

    def compose_body(self) -> ComposeResult:
        profile = mp.read_profile()

        yield Label("Observability", classes="field-label")
        # Two rows so every control stays visible on an 80-120 column terminal.
        with Horizontal(classes="form-row"):
            yield Label("enabled")
            yield Switch(value=profile.observability.enabled, id="obs-enabled")
            yield Label("emit cost")
            yield Switch(value=profile.observability.emit_cost, id="obs-emit-cost")
        with Horizontal(classes="form-row"):
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
            yield Button("PII demo", variant="primary", id="pii-demo")
            yield Button("Observability demo", id="obs-demo")

    def on_mount(self) -> None:
        # The Switch/Select widgets emit Changed events while mounting; enable
        # autosave only after the first refresh so those are not mistaken for
        # user edits and do not rewrite the profile on load.
        self.call_after_refresh(self._enable_autosave)

    def _enable_autosave(self) -> None:
        self._autosave = True

    def _persist(self) -> mp.MiddlewareProfile:
        # Start from the on-disk profile and change only the fields the form
        # exposes, so settings edited elsewhere (capabilities, entities, …) are
        # preserved rather than reset to defaults.
        current = mp.read_profile()
        profile = mp.MiddlewareProfile(
            observability=replace(
                current.observability,
                enabled=self.query_one("#obs-enabled", Switch).value,
                emit_cost=self.query_one("#obs-emit-cost", Switch).value,
                direction=self.query_one("#obs-direction", Select).value,
                log_level=self.query_one("#obs-log-level", Select).value,
            ),
            pii=replace(
                current.pii,
                enabled=self.query_one("#pii-enabled", Switch).value,
                strict_mode=self.query_one("#pii-strict", Switch).value,
                direction=self.query_one("#pii-direction", Select).value,
                detection_profile=self.query_one("#pii-profile", Select).value,
            ),
        )
        mp.write_profile(profile)
        return profile

    @on(Switch.Changed)
    @on(Select.Changed)
    def _on_form_change(self) -> None:
        # Apply every edit immediately so the profile the library reads always
        # matches what the form shows — no separate Save step to forget.
        if not self._autosave:
            return
        profile = self._persist()
        obs_state = "on" if profile.observability.enabled else "off"
        pii_state = "on" if profile.pii.enabled else "off"
        self.set_result(
            "result",
            f"Applied. Observability {obs_state}, PII redaction {pii_state}.",
        )

    @on(Button.Pressed, "#pii-demo")
    def _on_pii_demo(self) -> None:
        # Ensure PII is enabled so the config the redactor reads is active.
        profile = mp.read_profile()
        if not profile.pii.enabled:
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
            mp.write_profile(
                replace(profile, observability=replace(profile.observability, enabled=True))
            )
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
                "They are in the observability pane below (expanded for you; "
                "toggle with 'o')."
            )

        def show(text: str) -> None:
            self.set_result("result", text)
            # The obs pane is collapsed by default; expand and scroll it into
            # view so the events the demo just captured are actually visible,
            # even under tall controls on a short terminal.
            self.reveal_obs_panel()

        self.run_blocking(
            call,
            on_success=show,
            description=f"Observed completion via {state.current_engine(CAPABILITY)}",
        )
