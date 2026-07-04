"""Textual UI tests driven by the Pilot harness. All offline — no provider calls.

These cover mounting, navigation, readiness gating, and modal round-trips. The
real provider-call path is exercised by the shared worker helper but is not hit
here; readiness gating short-circuits before any network call.
"""

import pytest

pytest.importorskip("ai_api_unified")

from textual.widgets import DataTable, Input, Static  # noqa: E402

from sample_ai_api_unified.tui import app as tui_app  # noqa: E402
from sample_ai_api_unified.tui.app import SampleApp  # noqa: E402
from sample_ai_api_unified.tui.modals import (  # noqa: E402
    ChoiceModal,
    ConfirmModal,
    PromptModal,
)


@pytest.fixture()
def offline_env(monkeypatch):
    """Stop the app touching the real .env, and give a deterministic config."""
    monkeypatch.setattr(tui_app.envfile, "ensure_env_file", lambda: None)
    monkeypatch.setattr(tui_app.envfile, "reload_env", lambda: None)
    monkeypatch.setenv("COMPLETIONS_ENGINE", "google-gemini")
    monkeypatch.setenv("GOOGLE_AUTH_METHOD", "api_key")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "test-key")
    yield


async def test_default_screen_is_completions(offline_env):
    async with SampleApp().run_test() as pilot:
        assert pilot.app.query("CompletionsScreen")


async def test_keybindings_navigate(offline_env):
    async with SampleApp().run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()
        assert pilot.app.query("EmbeddingsScreen")
        await pilot.press("p")
        await pilot.pause()
        assert pilot.app.query("ProvidersScreen")
        await pilot.press("c")
        await pilot.pause()
        assert pilot.app.query("CompletionsScreen")


async def test_non_core_capability_shows_placeholder(offline_env):
    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen("videos")
        await pilot.pause()
        placeholder = pilot.app.query_one("PlaceholderScreen")
        assert "run-classic" in str(placeholder.query_one(".result-panel", Static).renderable)


async def test_readiness_gating(offline_env, monkeypatch):
    async with SampleApp().run_test() as pilot:
        assert pilot.app.ensure_capability_ready("completions") is True

        monkeypatch.delenv("COMPLETIONS_ENGINE", raising=False)
        assert pilot.app.ensure_capability_ready("completions") is False

        monkeypatch.setenv("COMPLETIONS_ENGINE", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert pilot.app.ensure_capability_ready("completions") is False


async def test_completions_empty_prompt_warns(offline_env):
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen._send("")
        await pilot.pause()
        assert "Enter a prompt" in str(screen.query_one("#result", Static).renderable)


async def test_completions_unconfigured_engine_warns(offline_env, monkeypatch):
    async with SampleApp().run_test() as pilot:
        monkeypatch.setenv("COMPLETIONS_ENGINE", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        screen = pilot.app.query_one("CompletionsScreen")
        screen._send("hello")
        await pilot.pause()
        assert "not configured" in str(screen.query_one("#result", Static).renderable)


async def test_providers_tables_populate(offline_env):
    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen("providers")
        await pilot.pause()
        config = pilot.app.query_one("#config-table", DataTable)
        status = pilot.app.query_one("#status-table", DataTable)
        assert config.row_count == 5  # five capabilities
        assert status.row_count == 5  # five providers


async def test_choice_modal_returns_selection(offline_env):
    async with SampleApp().run_test() as pilot:
        captured = {}
        pilot.app.push_screen(
            ChoiceModal("pick", [("Alpha", "a"), ("Beta", "b")]),
            lambda value: captured.setdefault("value", value),
        )
        await pilot.pause()
        await pilot.press("enter")  # highlighted first item
        await pilot.pause()
        assert captured["value"] == "a"


async def test_confirm_modal_returns_bool(offline_env):
    async with SampleApp().run_test() as pilot:
        captured = {}
        pilot.app.push_screen(
            ConfirmModal("sure?", default=True),
            lambda value: captured.setdefault("value", value),
        )
        await pilot.pause()
        await pilot.click("#no")
        await pilot.pause()
        assert captured["value"] is False


async def test_prompt_modal_returns_text(offline_env):
    async with SampleApp().run_test() as pilot:
        captured = {}
        pilot.app.push_screen(
            PromptModal("name?", default="seed"),
            lambda value: captured.setdefault("value", value),
        )
        await pilot.pause()
        pilot.app.query_one("#prompt-input", Input).value = "typed"
        await pilot.click("#ok")
        await pilot.pause()
        assert captured["value"] == "typed"


async def test_prompt_modal_cancel_returns_none(offline_env):
    async with SampleApp().run_test() as pilot:
        captured = {}
        pilot.app.push_screen(
            PromptModal("name?"),
            lambda value: captured.setdefault("value", value),
        )
        await pilot.pause()
        await pilot.click("#cancel")
        await pilot.pause()
        assert captured["value"] is None


async def test_onboarding_modal_saves_keys(offline_env, monkeypatch):
    from sample_ai_api_unified import catalog
    from sample_ai_api_unified.tui.modals import OnboardingModal

    saved = {}
    monkeypatch.setattr(
        "sample_ai_api_unified.tui.modals.onboarding.envfile.set_env_values", saved.update
    )
    monkeypatch.setattr(
        "sample_ai_api_unified.tui.modals.onboarding.envfile.reload_env", lambda: None
    )
    monkeypatch.setenv("ELEVEN_LABS_API_KEY", "")

    async with SampleApp().run_test() as pilot:
        captured = {}
        pilot.app.push_screen(
            OnboardingModal(catalog.PROVIDERS["elevenlabs"]),
            lambda ready: captured.setdefault("ready", ready),
        )
        await pilot.pause()
        pilot.app.query_one("#key-ELEVEN_LABS_API_KEY", Input).value = "sk-fake"
        await pilot.click("#save")
        await pilot.pause()
        assert saved == {"ELEVEN_LABS_API_KEY": "sk-fake"}
