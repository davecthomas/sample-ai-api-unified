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
from sample_ai_api_unified.tui.modals import ChoiceModal  # noqa: E402


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


@pytest.mark.parametrize(
    "key,screen_cls",
    [
        ("completions", "CompletionsScreen"),
        ("structured", "StructuredScreen"),
        ("embeddings", "EmbeddingsScreen"),
        ("images", "ImagesScreen"),
        ("videos", "VideosScreen"),
        ("voice", "VoiceScreen"),
        ("middleware", "MiddlewareScreen"),
        ("providers", "ProvidersScreen"),
    ],
)
async def test_every_capability_has_a_real_screen(offline_env, key, screen_cls):
    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen(key)
        await pilot.pause()
        assert pilot.app.query(screen_cls)


async def test_structured_gating(offline_env, monkeypatch):
    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen("structured")
        await pilot.pause()
        monkeypatch.setenv("COMPLETIONS_ENGINE", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        screen = pilot.app.query_one("StructuredScreen")
        await pilot.click("#contact")
        await pilot.pause()
        assert "not configured" in str(screen.query_one("#result", Static).renderable)


async def test_video_generate_prompts_for_confirmation(offline_env, monkeypatch):
    monkeypatch.setenv("VIDEO_ENGINE", "google-gemini")  # provider already configured
    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen("videos")
        await pilot.pause()
        screen = pilot.app.query_one("VideosScreen")
        screen.query_one("#prompt", Input).value = "a neon train at dusk"
        await pilot.click("#generate")
        await pilot.pause()
        assert pilot.app.query("ConfirmModal")  # cost confirmation before any call


async def test_middleware_save_writes_profile(offline_env, monkeypatch, tmp_path):
    from sample_ai_api_unified import middleware_profile as mp

    yaml_path = tmp_path / "middleware.yaml"
    monkeypatch.setattr(mp.paths, "MIDDLEWARE_YAML_PATH", yaml_path)
    monkeypatch.setattr(mp.envfile, "set_env_values", lambda values: None)

    async with SampleApp().run_test(size=(120, 50)) as pilot:
        pilot.app.show_screen("middleware")
        await pilot.pause()
        screen = pilot.app.query_one("MiddlewareScreen")
        from textual.widgets import Switch

        screen.query_one("#pii-enabled", Switch).value = True
        await pilot.click("#save")
        await pilot.pause()
        assert yaml_path.exists()
        profile = mp.read_profile(yaml_path)
        assert profile.pii.enabled is True


async def test_middleware_save_preserves_unshown_fields(offline_env, monkeypatch, tmp_path):
    """Saving from the form must not reset fields the form does not expose."""
    from sample_ai_api_unified import middleware_profile as mp

    yaml_path = tmp_path / "middleware.yaml"
    monkeypatch.setattr(mp.paths, "MIDDLEWARE_YAML_PATH", yaml_path)
    monkeypatch.setattr(mp.envfile, "set_env_values", lambda values: None)
    # A profile with a non-default field the form never shows.
    mp.write_profile(mp.MiddlewareProfile(pii=mp.PiiProfile(redact_entities=("EMAIL",))), yaml_path)

    async with SampleApp().run_test(size=(120, 50)) as pilot:
        pilot.app.show_screen("middleware")
        await pilot.pause()
        await pilot.click("#save")
        await pilot.pause()
        assert mp.read_profile(yaml_path).pii.redact_entities == ("EMAIL",)


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


async def test_worker_error_is_reported_not_fatal(offline_env):
    """A failing provider call shows the error and keeps the app alive.

    Regression: the thread worker must use exit_on_error=False, otherwise any
    provider exception tears the whole TUI down.
    """
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")

        def boom():
            raise RuntimeError("provider exploded")

        screen.run_blocking(boom, on_success=lambda _v: None, description="failing")
        text = ""
        for _ in range(50):
            await pilot.pause(0.05)
            text = str(screen.query_one("#result", Static).renderable)
            if "provider exploded" in text:
                break
        assert pilot.app.is_running  # app did not exit
        assert "RuntimeError" in text and "provider exploded" in text


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
