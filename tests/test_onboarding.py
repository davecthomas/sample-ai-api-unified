"""Provider credential status rows."""

from sample_ai_api_unified import onboarding


def test_status_rows_flag_missing_keys(monkeypatch):
    monkeypatch.delenv("ELEVEN_LABS_API_KEY", raising=False)
    rows = {label: (status, detail) for label, status, detail in onboarding.provider_status_rows()}
    status, detail = rows["ElevenLabs"]
    assert "missing" in status
    assert "ELEVEN_LABS_API_KEY" in detail


def test_status_rows_mark_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    rows = {label: status for label, status, _ in onboarding.provider_status_rows()}
    assert "configured" in rows["OpenAI"]
