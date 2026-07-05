"""Engine/model switching writes both the process env and .env."""

import pytest

from sample_ai_api_unified import state


@pytest.fixture()
def captured_env(monkeypatch):
    written = {}

    def fake_set(values):
        written.update(values)
        for name, value in values.items():
            monkeypatch.setenv(name, value)

    monkeypatch.setattr(state.envfile, "set_env_values", fake_set)
    return written


def test_set_engine_persists_engine_and_default_model(captured_env):
    state.set_engine("completions", "openai")
    assert captured_env["COMPLETIONS_ENGINE"] == "openai"
    assert captured_env["COMPLETIONS_MODEL_NAME"] == "gpt-4o-mini"


def test_set_engine_with_explicit_model(captured_env):
    state.set_engine("images", "google-gemini", "imagen-4.0-fast-generate-001")
    assert captured_env["IMAGE_ENGINE"] == "google-gemini"
    assert captured_env["IMAGE_MODEL_NAME"] == "imagen-4.0-fast-generate-001"


def test_set_engine_custom_selector_keeps_model_untouched(captured_env):
    state.set_engine("completions", "rerank")
    assert captured_env["COMPLETIONS_ENGINE"] == "rerank"
    assert "COMPLETIONS_MODEL_NAME" not in captured_env


def test_current_engine_and_model_read_environment(monkeypatch):
    monkeypatch.setenv("VIDEO_ENGINE", "openai")
    monkeypatch.setenv("VIDEO_MODEL_NAME", "sora-2-pro")
    assert state.current_engine("videos") == "openai"
    assert state.current_model("videos") == "sora-2-pro"


def test_capability_ready_with_configured_provider(monkeypatch):
    monkeypatch.setenv("COMPLETIONS_ENGINE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert state.capability_ready("completions") is True


def test_capability_ready_false_without_engine(monkeypatch):
    monkeypatch.delenv("COMPLETIONS_ENGINE", raising=False)
    assert state.capability_ready("completions") is False


def test_capability_ready_custom_engine_passes_through(monkeypatch):
    monkeypatch.setenv("COMPLETIONS_ENGINE", "some-future-engine")
    assert state.capability_ready("completions") is True


def test_voice_model_hidden_for_non_google_engines(monkeypatch):
    monkeypatch.setenv("DEFAULT_GEMINI_TTS_MODEL", "gemini-2.5-pro-tts")
    monkeypatch.setenv("AI_VOICE_ENGINE", "openai")
    assert state.current_model("voice") == ""
    monkeypatch.setenv("AI_VOICE_ENGINE", "google")
    assert state.current_model("voice") == "gemini-2.5-pro-tts"


def test_ensure_supported_model_heals_unavailable_preview(captured_env, monkeypatch):
    monkeypatch.setenv("VIDEO_ENGINE", "google-gemini")
    # A model the library lists but Vertex 404s on (in UNAVAILABLE_MODELS).
    monkeypatch.setenv("VIDEO_MODEL_NAME", "veo-3.1-lite-generate-preview")
    assert state.ensure_supported_model("videos") == "veo-3.0-fast-generate-001"
    assert captured_env["VIDEO_MODEL_NAME"] == "veo-3.0-fast-generate-001"


def test_ensure_supported_model_sets_default_when_unset(captured_env, monkeypatch):
    monkeypatch.setenv("VIDEO_ENGINE", "google-gemini")
    monkeypatch.delenv("VIDEO_MODEL_NAME", raising=False)
    assert state.ensure_supported_model("videos") == "veo-3.0-fast-generate-001"
    assert captured_env["VIDEO_MODEL_NAME"] == "veo-3.0-fast-generate-001"


def test_ensure_supported_model_keeps_a_valid_cataloged_model(captured_env, monkeypatch):
    monkeypatch.setenv("VIDEO_ENGINE", "google-gemini")
    monkeypatch.setenv("VIDEO_MODEL_NAME", "veo-2.0-generate-001")
    assert state.ensure_supported_model("videos") == "veo-2.0-generate-001"
    assert "VIDEO_MODEL_NAME" not in captured_env  # no rewrite for a valid model


def test_ensure_supported_model_preserves_custom_model(captured_env, monkeypatch):
    # A model the user set that is neither cataloged nor known-unavailable must
    # survive — the custom-model escape hatch (ADR-0002).
    monkeypatch.setenv("VIDEO_ENGINE", "google-gemini")
    monkeypatch.setenv("VIDEO_MODEL_NAME", "veo-9.9-experimental-001")
    assert state.ensure_supported_model("videos") == "veo-9.9-experimental-001"
    assert "VIDEO_MODEL_NAME" not in captured_env  # left untouched


def test_ensure_supported_model_leaves_custom_engine_untouched(captured_env, monkeypatch):
    monkeypatch.setenv("VIDEO_ENGINE", "some-future-engine")
    monkeypatch.setenv("VIDEO_MODEL_NAME", "whatever")
    assert state.ensure_supported_model("videos") == "whatever"
    assert "VIDEO_MODEL_NAME" not in captured_env


def test_google_voice_engine_selection_preserves_tts_model(captured_env, monkeypatch):
    monkeypatch.setenv("DEFAULT_GEMINI_TTS_MODEL", "gemini-2.5-flash-tts")
    state.set_engine("voice", "google")
    assert "DEFAULT_GEMINI_TTS_MODEL" not in captured_env  # no silent overwrite
