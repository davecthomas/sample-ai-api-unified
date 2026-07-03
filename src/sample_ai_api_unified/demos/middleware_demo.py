"""Middleware demos: profile editing, PII redaction, live observability."""

from __future__ import annotations

from dataclasses import replace

from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .. import middleware_profile, obs, paths, runner, samples, state, ui
from ..guard import provider_errors


def _ensure_pii_enabled() -> bool:
    profile = middleware_profile.read_profile()
    if profile.pii.enabled and paths.MIDDLEWARE_YAML_PATH.exists():
        return True
    if not ui.confirm("PII redaction is currently off. Enable it now?", default=True):
        return False
    profile = replace(profile, pii=replace(profile.pii, enabled=True))
    middleware_profile.write_profile(profile)
    ui.success("PII redaction enabled (input_only by default).")
    return True


def _ensure_observability_enabled() -> bool:
    profile = middleware_profile.read_profile()
    if profile.observability.enabled and paths.MIDDLEWARE_YAML_PATH.exists():
        return True
    if not ui.confirm("Observability is currently off. Enable it now?", default=True):
        return False
    profile = replace(profile, observability=replace(profile.observability, enabled=True))
    middleware_profile.write_profile(profile)
    ui.success("Observability enabled.")
    return True


def _show_profile() -> None:
    profile = middleware_profile.read_profile()
    table = Table(title="Active middleware profile", border_style="cyan")
    table.add_column("Middleware", style="bold")
    table.add_column("Enabled")
    table.add_column("Key settings", style="dim")
    table.add_row(
        "observability",
        str(profile.observability.enabled),
        f"direction={profile.observability.direction}, "
        f"log_level={profile.observability.log_level}, "
        f"capabilities={', '.join(profile.observability.capabilities) or 'all'}",
    )
    table.add_row(
        "pii_redaction",
        str(profile.pii.enabled),
        f"direction={profile.pii.direction}, profile={profile.pii.detection_profile}, "
        f"strict={profile.pii.strict_mode}, redacting {len(profile.pii.redact_entities)} entity types",
    )
    ui.console.print(table)
    if paths.MIDDLEWARE_YAML_PATH.exists():
        ui.info(f"Generated YAML at {paths.MIDDLEWARE_YAML_PATH}:")
        ui.console.print(Syntax(paths.MIDDLEWARE_YAML_PATH.read_text(), "yaml", theme="ansi_dark"))
    else:
        ui.warn("No profile saved yet — pick 'Edit middleware profile' and save.")


def _pii_local_demo() -> None:
    """Run fake-PII strings through the redactor and show before/after."""
    if not _ensure_pii_enabled():
        return
    with provider_errors():
        from ai_api_unified.middleware.pii_redactor import AiApiPiiMiddleware

        redactor = AiApiPiiMiddleware()
        table = Table(title="PII redaction (all PII is fabricated)", border_style="magenta")
        table.add_column("Original", max_width=48)
        table.add_column("Redacted", max_width=48)
        for sample in samples.PII_SAMPLES:
            redacted = runner.run_call(
                "Redacting sample", lambda s=sample: redactor.process_input(s)
            )
            table.add_row(sample, redacted)
        ui.console.print(table)


def _pii_live_demo() -> None:
    """Prove redaction happens before the provider sees the prompt."""
    if not _ensure_pii_enabled():
        return
    if not state.ensure_capability_ready("completions"):
        return
    sample = samples.PII_SAMPLES[0]
    prompt = (
        "Repeat the following text back to me exactly, character for character, "
        f"with no commentary: {sample}"
    )
    ui.info(
        "The completions client redacts the prompt before sending, so the model's "
        "echo reveals exactly what the provider received."
    )
    with provider_errors():
        from ai_api_unified import AIFactory

        client = AIFactory.get_ai_completions_client()
        response = runner.run_call(
            f"Echo test via {state.current_engine('completions')}",
            lambda: client.send_prompt(prompt),
        )
        ui.console.print(Panel(sample, title="What you asked to send", border_style="red"))
        ui.console.print(Panel(response, title="What the model echoed back", border_style="green"))


def _observability_demo() -> None:
    """Run a cheap completion and show the emitted metadata events."""
    if not _ensure_observability_enabled():
        return
    if not state.ensure_capability_ready("completions"):
        return
    with provider_errors():
        from ai_api_unified import AIFactory
        from ai_api_unified.middleware import set_observability_context

        set_observability_context(
            caller_id="sample-app", session_id="console-demo", workflow_id="observability-demo"
        )
        obs.clear()
        client = AIFactory.get_ai_completions_client()
        response = runner.run_call(
            "Observed completion",
            lambda: client.send_prompt("Reply with the single word: observed"),
        )
        ui.info(f"Model replied: {response.strip()}")
        events = obs.all_events()
        if events:
            ui.success(
                f"Captured {len(events)} observability events (metadata only — "
                "no prompt or response text is ever logged)."
            )
        else:
            ui.warn(
                "No events captured — check that observability is enabled and the "
                "completions capability is included in the profile."
            )


def run() -> None:
    while True:
        ui.header("Middleware", "observability + PII redaction, configured from menus")
        picked = ui.choose(
            "Middleware demos",
            [
                ui.MenuOption("Edit middleware profile", "edit", "menus generate the YAML"),
                ui.MenuOption("Show active profile", "show"),
                ui.MenuOption("PII redaction: before/after samples", "pii_local"),
                ui.MenuOption("PII redaction: live completion echo test", "pii_live"),
                ui.MenuOption("Observability: live event capture", "observability"),
            ],
        )
        if picked is None:
            return
        if picked.value == "edit":
            middleware_profile.edit_profile()
        elif picked.value == "show":
            _show_profile()
        elif picked.value == "pii_local":
            _pii_local_demo()
        elif picked.value == "pii_live":
            _pii_live_demo()
        elif picked.value == "observability":
            _observability_demo()
