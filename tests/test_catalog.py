"""Catalog integrity: engines, providers, and env keys stay consistent."""

from sample_ai_api_unified import catalog

# Engine selector strings accepted by the library's provider registry.
VALID_SELECTORS = {
    "completions": {
        "openai",
        "google-gemini",
        "llama",
        "anthropic",
        "mistral",
        "nova",
        "cohere",
        "ai21",
        "rerank",
        "canvas",
    },
    "embeddings": {"openai", "titan", "google-gemini"},
    "images": {"openai", "bedrock", "nova", "nova-canvas", "google-gemini"},
    "videos": {"openai", "google-gemini", "bedrock", "nova", "nova-reel"},
    "voice": {"openai", "google", "azure", "elevenlabs"},
}


def test_every_engine_selector_is_registry_valid():
    for key, capability in catalog.CAPABILITIES.items():
        for engine in capability.engines:
            assert (
                engine.selector in VALID_SELECTORS[key]
            ), f"{engine.selector} is not a valid {key} selector"


def test_every_engine_maps_to_a_known_provider():
    for capability in catalog.CAPABILITIES.values():
        for engine in capability.engines:
            assert engine.provider in catalog.PROVIDERS


def test_default_models_are_listed():
    for capability in catalog.CAPABILITIES.values():
        for engine in capability.engines:
            if engine.default_model:
                assert engine.default_model in engine.models


def test_missing_keys_detection(monkeypatch):
    provider = catalog.PROVIDERS["openai"]
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert [key.name for key in catalog.missing_keys(provider)] == ["OPENAI_API_KEY"]
    assert not catalog.provider_configured(provider)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert catalog.provider_configured(provider)


def test_optional_keys_do_not_block_configuration(monkeypatch):
    provider = catalog.PROVIDERS["aws"]
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    assert catalog.provider_configured(provider)


def test_provider_for_engine():
    provider = catalog.provider_for_engine("completions", "anthropic")
    assert provider is not None and provider.key == "aws"
    assert catalog.provider_for_engine("completions", "not-a-real-engine") is None
