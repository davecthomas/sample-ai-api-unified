"""Runtime engine/model selection.

The library resolves engines and models from the environment on every factory
call, so switching providers is just: update os.environ (and .env so the
choice persists), then let the next factory call pick it up.
"""

from __future__ import annotations

import os

from rich.table import Table

from . import catalog, envfile, onboarding, ui


def current_engine(capability_key: str) -> str:
    return os.environ.get(catalog.CAPABILITIES[capability_key].engine_env, "")


def current_model(capability_key: str) -> str:
    # DEFAULT_GEMINI_TTS_MODEL only applies to the google voice engine; showing
    # it as the model for openai/azure/elevenlabs voice would be misleading.
    if capability_key == "voice" and current_engine("voice") != "google":
        return ""
    return os.environ.get(catalog.CAPABILITIES[capability_key].model_env, "")


def set_engine(capability_key: str, selector: str, model: str = "") -> None:
    capability = catalog.CAPABILITIES[capability_key]
    values = {capability.engine_env: selector}
    engine = catalog.engine_for(capability_key, selector)
    chosen_model = model or (engine.default_model if engine else "")
    if chosen_model:
        values[capability.model_env] = chosen_model
    envfile.set_env_values(values)


def set_model(capability_key: str, model: str) -> None:
    envfile.set_env_values({catalog.CAPABILITIES[capability_key].model_env: model})


def switch_engine_menu(capability_key: str) -> bool:
    """Interactive engine switch. Returns True if the engine is ready to use."""
    capability = catalog.CAPABILITIES[capability_key]
    options = []
    for engine in capability.engines:
        provider = catalog.PROVIDERS[engine.provider]
        status = "" if catalog.provider_configured(provider) else "needs API key"
        hint = "; ".join(part for part in (engine.note, status) if part)
        options.append(ui.MenuOption(f"{engine.selector} ({provider.label})", engine, hint))
    options.append(ui.MenuOption("Custom engine selector…", "custom"))

    picked = ui.choose(f"{capability.label}: choose engine", options)
    if picked is None:
        return False
    if picked.value == "custom":
        selector = ui.ask("Engine selector (as accepted by the library)")
        if not selector:
            return False
        set_engine(capability_key, selector)
        return True

    engine: catalog.Engine = picked.value
    if not onboarding.ensure_engine_ready(capability_key, engine.selector):
        return False
    set_engine(capability_key, engine.selector)
    if engine.models:
        switch_model_menu(capability_key)
    ui.success(f"{capability.label} engine set to {engine.selector}")
    return True


def switch_model_menu(capability_key: str) -> None:
    capability = catalog.CAPABILITIES[capability_key]
    engine = catalog.engine_for(capability_key, current_engine(capability_key))
    models = list(engine.models) if engine else []
    options = [
        ui.MenuOption(m, m, "default" if engine and m == engine.default_model else "")
        for m in models
    ]
    options.append(ui.MenuOption("Custom model name…", "custom"))
    picked = ui.choose(f"{capability.label}: choose model", options)
    if picked is None:
        return
    model = ui.ask("Model name") if picked.value == "custom" else str(picked.value)
    if model:
        set_model(capability_key, model)
        ui.success(f"{capability.label} model set to {model}")


def ensure_capability_ready(capability_key: str) -> bool:
    """Make sure an engine is selected and its provider has credentials."""
    selector = current_engine(capability_key)
    if not selector:
        ui.warn(f"No engine selected for {catalog.CAPABILITIES[capability_key].label} yet.")
        return switch_engine_menu(capability_key)
    return onboarding.ensure_engine_ready(capability_key, selector)


def show_configuration() -> None:
    table = Table(title="Current configuration", border_style="cyan")
    table.add_column("Capability", style="bold")
    table.add_column("Engine")
    table.add_column("Model")
    for key, capability in catalog.CAPABILITIES.items():
        table.add_row(
            capability.label,
            current_engine(key) or "[dim]unset[/dim]",
            current_model(key) or "[dim]provider default[/dim]",
        )
    ui.console.print(table)

    status = Table(title="Provider credentials", border_style="cyan")
    status.add_column("Provider", style="bold")
    status.add_column("Status")
    status.add_column("Detail", style="dim")
    for label, state_text, detail in onboarding.provider_status_rows():
        status.add_row(label, state_text, detail)
    ui.console.print(status)
