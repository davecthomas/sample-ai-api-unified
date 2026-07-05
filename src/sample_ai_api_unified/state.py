"""Runtime engine/model selection.

The library resolves engines and models from the environment on every factory
call, so switching providers is: update os.environ (and .env so the choice
persists), then let the next factory call pick it up.
"""

from __future__ import annotations

import contextlib
import os

from . import catalog, envfile


@contextlib.contextmanager
def temp_env(**overrides: str):
    """Apply env-var overrides for the duration of a call, then restore them.

    Used to run a Google call that needs api-key auth (e.g. video download via
    the Files API, or multimodal media embeddings) under a temporary config
    without persisting anything to ``.env``, so a cancelled or failed call never
    changes the user's saved defaults. The library reads these from the
    environment on each factory call. (Single-user app: the override is
    process-global for the call's duration, which is fine here.)
    """
    previous = {name: os.environ.get(name) for name in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


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


# Models the library still lists as supported but that are not deployed on the
# provider (they 404). A persisted or defaulted value here is healed to the
# engine's GA default; any other value the user set is left alone so the
# custom-model escape hatch (ADR-0002) keeps working.
UNAVAILABLE_MODELS: frozenset[str] = frozenset(
    {
        "veo-3.1-generate-preview",
        "veo-3.1-fast-generate-preview",
        "veo-3.1-lite-generate-preview",
    }
)


def resolve_model(capability_key: str) -> tuple[str, bool]:
    """Resolve the model to use for the current engine without writing anything.

    Returns ``(model, needs_persist)``. The library reads the model from the
    environment on every factory call and falls back to its own default when the
    variable is unset — and that default can be a model that no longer runs. So
    when the persisted model is unset or a known-unavailable model, resolve to
    the engine's default and flag that it should be persisted. Custom engines
    and user-chosen custom models are left as-is.
    """
    selector = current_engine(capability_key)
    if not selector:
        return "", False
    engine = catalog.engine_for(capability_key, selector)
    if engine is None or not engine.default_model:
        return current_model(capability_key), False  # custom/unknown engine
    model = current_model(capability_key)
    if (not model or model in UNAVAILABLE_MODELS) and model != engine.default_model:
        return engine.default_model, True
    return model, False


def ensure_supported_model(capability_key: str) -> str:
    """Resolve the model for the current engine, persisting a heal if needed.

    Call this before a factory call so the library never falls back to its own
    (possibly 404) default. For read-only display use ``resolve_model``.
    """
    model, needs_persist = resolve_model(capability_key)
    if needs_persist:
        set_model(capability_key, model)
    return model


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
