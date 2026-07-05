"""Runtime engine/model selection.

The library resolves engines and models from the environment on every factory
call, so switching providers is: update os.environ (and .env so the choice
persists), then let the next factory call pick it up.
"""

from __future__ import annotations

import os

from . import catalog, envfile


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


def capability_ready(capability_key: str) -> bool:
    """True when an engine is selected and its provider has credentials.

    Non-interactive: onboarding happens on the Providers screen.
    """
    selector = current_engine(capability_key)
    if not selector:
        return False
    provider = catalog.provider_for_engine(capability_key, selector)
    if provider is None:
        return True  # custom selector; let the library validate it
    return catalog.provider_configured(provider)
