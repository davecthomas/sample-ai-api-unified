"""API-key onboarding: status rows, save path, and decline path."""

import pytest

from sample_ai_api_unified import catalog, onboarding


def feed(monkeypatch, lines):
    iterator = iter(lines)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(iterator))


@pytest.fixture()
def captured_env(monkeypatch):
    written = {}

    def fake_set(values):
        written.update(values)
        for name, value in values.items():
            monkeypatch.setenv(name, value)

    monkeypatch.setattr(onboarding.envfile, "set_env_values", fake_set)
    monkeypatch.setattr(onboarding.envfile, "reload_env", lambda: None)
    return written


def test_status_rows_flag_missing_keys(monkeypatch):
    monkeypatch.delenv("ELEVEN_LABS_API_KEY", raising=False)
    rows = {label: (status, detail) for label, status, detail in onboarding.provider_status_rows()}
    status, detail = rows["ElevenLabs"]
    assert "missing" in status
    assert "ELEVEN_LABS_API_KEY" in detail


def test_already_configured_provider_short_circuits(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert onboarding.ensure_provider_ready(catalog.PROVIDERS["openai"]) is True


def test_key_entry_saves_and_reports_ready(monkeypatch, captured_env):
    monkeypatch.delenv("ELEVEN_LABS_API_KEY", raising=False)
    # browser? no; enter now? yes; then the key value
    feed(monkeypatch, ["n", "y", "fake-key"])
    assert onboarding.ensure_provider_ready(catalog.PROVIDERS["elevenlabs"]) is True
    assert captured_env == {"ELEVEN_LABS_API_KEY": "fake-key"}


def test_decline_leaves_env_untouched(monkeypatch, captured_env):
    monkeypatch.delenv("ELEVEN_LABS_API_KEY", raising=False)
    feed(monkeypatch, ["n", "n"])
    assert onboarding.ensure_provider_ready(catalog.PROVIDERS["elevenlabs"]) is False
    assert captured_env == {}


def test_blank_required_key_aborts(monkeypatch, captured_env):
    monkeypatch.delenv("ELEVEN_LABS_API_KEY", raising=False)
    feed(monkeypatch, ["n", "y", ""])
    assert onboarding.ensure_provider_ready(catalog.PROVIDERS["elevenlabs"]) is False
    assert captured_env == {}


def test_optional_keys_can_be_skipped(monkeypatch, captured_env):
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_REGION"):
        monkeypatch.delenv(key, raising=False)
    # browser? no; enter? yes; access key; secret; session token skipped; region default
    feed(monkeypatch, ["n", "y", "AKIATEST", "secret123", "", ""])
    assert onboarding.ensure_provider_ready(catalog.PROVIDERS["aws"]) is True
    assert captured_env["AWS_ACCESS_KEY_ID"] == "AKIATEST"
    assert captured_env["AWS_SECRET_ACCESS_KEY"] == "secret123"
    assert "AWS_SESSION_TOKEN" not in captured_env
    assert captured_env["AWS_REGION"] == "us-east-1"
