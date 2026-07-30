"""Shared pytest fixtures for the TUI tests."""

import pytest

pytest.importorskip("ai_api_unified")

from sample_ai_api_unified.tui import app as tui_app  # noqa: E402


@pytest.fixture()
def offline_env(monkeypatch, tmp_path):
    """Stop the app touching the real .env, and give a deterministic config."""
    monkeypatch.setattr(tui_app.envfile, "ensure_env_file", lambda: None)
    monkeypatch.setattr(tui_app.envfile, "reload_env", lambda: None)
    # Don't create the real ./logs dir or attach a file handler during UI tests;
    # obs.enable_file_logging is covered directly in test_obs.
    monkeypatch.setattr(
        tui_app.obs, "enable_file_logging", lambda *a, **k: tmp_path / "session.log"
    )
    # Redirect any .env write (e.g. a model heal) to a throwaway file so no test
    # can mutate the developer's real .env in the repo root.
    from sample_ai_api_unified import paths

    monkeypatch.setattr(paths, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setenv("COMPLETIONS_ENGINE", "google-gemini")
    monkeypatch.setenv("GOOGLE_AUTH_METHOD", "api_key")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "test-key")
    yield
