"""Textual UI tests driven by the Pilot harness. All offline — no provider calls.

These cover mounting, navigation, readiness gating, and modal round-trips. The
real provider-call path is exercised by the shared worker helper but is not hit
here; readiness gating short-circuits before any network call.
"""

import os

import pytest

pytest.importorskip("ai_api_unified")

from textual.widgets import DataTable, Input, Static  # noqa: E402

from sample_ai_api_unified.tui import app as tui_app  # noqa: E402
from sample_ai_api_unified.tui.app import SampleApp  # noqa: E402
from sample_ai_api_unified.tui.modals import ChoiceModal  # noqa: E402


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


def _configured_service_account(monkeypatch, tmp_path):
    """A service-account Google setup: auth mode plus an existing creds file."""
    creds = tmp_path / "sa.json"
    creds.write_text("{}")
    monkeypatch.setenv("GOOGLE_AUTH_METHOD", "service_account")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds))


async def test_video_google_service_account_without_key_warns(offline_env, monkeypatch, tmp_path):
    # Google video download needs the Files API (api-key auth); on a service
    # account with no Gemini key there is nothing to switch to, so it warns and
    # does not reach the cost confirmation.
    monkeypatch.setenv("VIDEO_ENGINE", "google-gemini")
    _configured_service_account(monkeypatch, tmp_path)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen("videos")
        await pilot.pause()
        screen = pilot.app.query_one("VideosScreen")
        screen.query_one("#prompt", Input).value = "a neon train at dusk"
        await pilot.click("#generate")
        await pilot.pause()
        assert not pilot.app.query("ConfirmModal")  # never reaches the cost prompt
        assert "Files API" in str(screen.query_one("#result", Static).renderable)


async def test_video_google_service_account_with_key_proceeds(offline_env, monkeypatch, tmp_path):
    # Service account plus a Gemini key: it proceeds to the cost confirmation
    # (the call will run under a temporary api_key override).
    monkeypatch.setenv("VIDEO_ENGINE", "google-gemini")
    _configured_service_account(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "test-key")
    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen("videos")
        await pilot.pause()
        screen = pilot.app.query_one("VideosScreen")
        screen.query_one("#prompt", Input).value = "a neon train at dusk"
        await pilot.click("#generate")
        await pilot.pause()
        assert pilot.app.query("ConfirmModal")


async def test_middleware_edit_persists_immediately(offline_env, monkeypatch, tmp_path):
    """Toggling a form control writes the profile without a separate Save step."""
    from sample_ai_api_unified import middleware_profile as mp

    yaml_path = tmp_path / "middleware.yaml"
    monkeypatch.setattr(mp.paths, "MIDDLEWARE_YAML_PATH", yaml_path)
    monkeypatch.setattr(mp.envfile, "set_env_values", lambda values: None)

    async with SampleApp().run_test(size=(120, 50)) as pilot:
        pilot.app.show_screen("middleware")
        await pilot.pause()
        await pilot.pause()  # let call_after_refresh enable autosave
        screen = pilot.app.query_one("MiddlewareScreen")
        from textual.widgets import Switch

        assert screen._autosave is True
        screen.query_one("#pii-enabled", Switch).value = True
        await pilot.pause()
        assert yaml_path.exists()
        assert mp.read_profile(yaml_path).pii.enabled is True


async def test_middleware_disable_pii_persists(offline_env, monkeypatch, tmp_path):
    """Disabling PII redaction takes effect immediately (regression: the switch
    used to persist only on a Save click, so a disabled switch was ignored)."""
    from sample_ai_api_unified import middleware_profile as mp

    yaml_path = tmp_path / "middleware.yaml"
    monkeypatch.setattr(mp.paths, "MIDDLEWARE_YAML_PATH", yaml_path)
    monkeypatch.setattr(mp.envfile, "set_env_values", lambda values: None)
    mp.write_profile(mp.MiddlewareProfile(pii=mp.PiiProfile(enabled=True)), yaml_path)

    async with SampleApp().run_test(size=(120, 50)) as pilot:
        pilot.app.show_screen("middleware")
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.query_one("MiddlewareScreen")
        from textual.widgets import Switch

        screen.query_one("#pii-enabled", Switch).value = False
        await pilot.pause()
        assert mp.read_profile(yaml_path).pii.enabled is False


async def test_middleware_mount_does_not_rewrite(offline_env, monkeypatch, tmp_path):
    """Widgets fire Changed events while mounting; those must not autosave and
    clobber the on-disk profile before the user edits anything."""
    from sample_ai_api_unified import middleware_profile as mp

    yaml_path = tmp_path / "middleware.yaml"
    monkeypatch.setattr(mp.paths, "MIDDLEWARE_YAML_PATH", yaml_path)
    monkeypatch.setattr(mp.envfile, "set_env_values", lambda values: None)
    original = mp.MiddlewareProfile(pii=mp.PiiProfile(enabled=True, redact_entities=("EMAIL",)))
    mp.write_profile(original, yaml_path)
    mtime = yaml_path.stat().st_mtime_ns

    async with SampleApp().run_test(size=(120, 50)) as pilot:
        pilot.app.show_screen("middleware")
        await pilot.pause()
        await pilot.pause()
        # No edit made — the file must be byte-for-byte untouched.
        assert yaml_path.stat().st_mtime_ns == mtime
        assert mp.read_profile(yaml_path).pii.enabled is True


async def test_middleware_edit_preserves_unshown_fields(offline_env, monkeypatch, tmp_path):
    """Auto-applying an edit must not reset fields the form does not expose."""
    from sample_ai_api_unified import middleware_profile as mp

    yaml_path = tmp_path / "middleware.yaml"
    monkeypatch.setattr(mp.paths, "MIDDLEWARE_YAML_PATH", yaml_path)
    monkeypatch.setattr(mp.envfile, "set_env_values", lambda values: None)
    # A profile with a non-default field the form never shows.
    mp.write_profile(mp.MiddlewareProfile(pii=mp.PiiProfile(redact_entities=("EMAIL",))), yaml_path)

    async with SampleApp().run_test(size=(120, 50)) as pilot:
        pilot.app.show_screen("middleware")
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.query_one("MiddlewareScreen")
        from textual.widgets import Switch

        screen.query_one("#pii-strict", Switch).value = True  # trigger an autosave
        await pilot.pause()
        assert mp.read_profile(yaml_path).pii.redact_entities == ("EMAIL",)


@pytest.mark.parametrize(
    "key",
    [
        "completions",
        "structured",
        "embeddings",
        "images",
        "videos",
        "voice",
        "middleware",
        "providers",
    ],
)
async def test_result_region_and_collapsed_obs_on_every_screen(offline_env, key):
    from textual.widgets import Collapsible

    async with SampleApp().run_test(size=(120, 44)) as pilot:
        pilot.app.show_screen(key)
        await pilot.pause()
        screen = pilot.app.query_one(
            f"{key.capitalize() if key != 'providers' else 'Providers'}Screen"
        )
        # The base owns a single scrollable result region below the controls.
        assert screen.query_one("#result", Static) is not None
        # Observability lives in a Collapsible that starts collapsed.
        obs_panel = screen.query_one("#obs-panel", Collapsible)
        assert obs_panel.collapsed is True


async def test_obs_toggle_binding_expands_and_collapses(offline_env):
    from textual.widgets import Collapsible

    async with SampleApp().run_test(size=(120, 44)) as pilot:
        panel = pilot.app.query_one("#obs-panel", Collapsible)
        assert panel.collapsed is True
        await pilot.press("o")
        await pilot.pause()
        assert pilot.app.query_one("#obs-panel", Collapsible).collapsed is False
        await pilot.press("o")
        await pilot.pause()
        assert pilot.app.query_one("#obs-panel", Collapsible).collapsed is True


async def test_obs_pane_visible_when_expanded_on_short_terminal(offline_env):
    """Regression: on a short terminal the completions controls fill the screen,
    so before the scrolling-column layout the expanded obs pane rendered below
    the fold and looked blank. Expanding must scroll it fully into view."""
    from sample_ai_api_unified.tui.widgets.obs_log import ObservabilityLog

    async with SampleApp().run_test(size=(100, 24)) as pilot:
        pilot.app.show_screen("completions")
        await pilot.pause()
        screen = pilot.app.query_one("CompletionsScreen")
        screen.set_result("result", "\n".join(f"line {i}" for i in range(40)))
        log = pilot.app.query_one(ObservabilityLog)
        for i in range(30):
            log.write(f"event #{i}")
        await pilot.pause()
        # Expand + scroll into view the way the 'o' binding now does.
        pilot.app.action_toggle_obs()
        await pilot.pause()
        await pilot.pause()
        region = log.region
        screen_height = 24
        assert region.height > 0
        assert region.y >= 0
        # The whole log sits within the viewport, not clipped off the bottom.
        assert region.y + region.height <= screen_height


async def test_generate_prompt_reveals_obs_pane(offline_env, monkeypatch):
    """Generating a prompt is a completions call that emits observability events,
    so it must reveal the (collapsed-by-default) pane to surface them."""
    from textual.widgets import Collapsible

    from sample_ai_api_unified import promptgen

    monkeypatch.setattr(promptgen, "generate_prompt", lambda kind: f"generated for {kind}")

    async with SampleApp().run_test(size=(120, 44)) as pilot:
        pilot.app.show_screen("completions")
        await pilot.pause()
        assert pilot.app.query_one("#obs-panel", Collapsible).collapsed is True
        await pilot.click("#generate")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert pilot.app.query_one("#obs-panel", Collapsible).collapsed is False


async def test_set_result_updates_result_region(offline_env):
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen.set_result("result", "a long response body")
        await pilot.pause()
        assert "a long response body" in str(screen.query_one("#result", Static).renderable)


async def test_obs_demo_expands_the_pane(offline_env, monkeypatch, tmp_path):
    """The observability demo captures events into the pane, so it must expand
    the collapsed-by-default pane to make them visible."""
    import ai_api_unified

    from sample_ai_api_unified import middleware_profile as mp

    yaml_path = tmp_path / "middleware.yaml"
    monkeypatch.setattr(mp.paths, "MIDDLEWARE_YAML_PATH", yaml_path)
    monkeypatch.setattr(mp.envfile, "set_env_values", lambda values: None)

    class _FakeCompletions:
        def send_prompt(self, prompt: str) -> str:
            return "observed"

    monkeypatch.setattr(
        ai_api_unified.AIFactory,
        "get_ai_completions_client",
        staticmethod(lambda: _FakeCompletions()),
    )

    from textual.widgets import Collapsible

    async with SampleApp().run_test(size=(120, 50)) as pilot:
        pilot.app.show_screen("middleware")
        await pilot.pause()
        assert pilot.app.query_one("#obs-panel", Collapsible).collapsed is True
        await pilot.click("#obs-demo")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert pilot.app.query_one("#obs-panel", Collapsible).collapsed is False


async def test_copy_result_copies_markup_free_error_text(offline_env, monkeypatch):
    from sample_ai_api_unified import clipboard

    captured = {}
    monkeypatch.setattr(
        clipboard, "copy_to_clipboard", lambda text: captured.update(text=text) or True
    )
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen.set_result("result", "[red]RuntimeError: 404 NOT_FOUND[/red]")
        await pilot.pause()
        # The stored copy text has the Rich markup stripped.
        assert screen._last_result == "RuntimeError: 404 NOT_FOUND"
        await pilot.press("y")
        await pilot.pause()
        # The system clipboard (pbcopy/xclip/…) receives the markup-free text.
        assert captured["text"] == "RuntimeError: 404 NOT_FOUND"


async def test_copy_result_falls_back_to_osc52(offline_env, monkeypatch):
    from sample_ai_api_unified import clipboard

    # No OS clipboard tool available → fall back to the terminal OSC 52 path.
    monkeypatch.setattr(clipboard, "copy_to_clipboard", lambda text: False)
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen.set_result("result", "boom")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert pilot.app.clipboard == "boom"


async def test_multimodal_warns_service_account_without_key(offline_env, monkeypatch):
    # Service-account auth cannot do media embeddings, and with no Gemini API key
    # there is nothing to temporarily switch to — so it must warn.
    monkeypatch.setenv("GOOGLE_AUTH_METHOD", "service_account")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        pilot.app.show_screen("embeddings")
        await pilot.pause()
        screen = pilot.app.query_one("EmbeddingsScreen")
        await pilot.click("#multimodal")
        await pilot.pause()
        result = str(screen.query_one("#result", Static).renderable)
        assert "API-key auth" in result and "GOOGLE_GEMINI_API_KEY" in result


async def test_multimodal_service_account_with_key_proceeds(offline_env, monkeypatch):
    # Service account plus a Gemini API key: the demo proceeds to the image
    # picker (it will run under a temporary api_key override), no warning.
    monkeypatch.setenv("GOOGLE_AUTH_METHOD", "service_account")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "test-key")
    async with SampleApp().run_test(size=(140, 44)) as pilot:
        pilot.app.show_screen("embeddings")
        await pilot.pause()
        screen = pilot.app.query_one("EmbeddingsScreen")
        await pilot.click("#multimodal")
        await pilot.pause()
        assert "API-key auth" not in str(screen.query_one("#result", Static).renderable)
        assert pilot.app.query("ChoiceModal")  # advanced to picking an image


def test_temp_env_restores_previous_value(monkeypatch):
    from sample_ai_api_unified import state

    monkeypatch.setenv("GOOGLE_AUTH_METHOD", "service_account")
    with state.temp_env(GOOGLE_AUTH_METHOD="api_key"):
        assert os.environ["GOOGLE_AUTH_METHOD"] == "api_key"
    assert os.environ["GOOGLE_AUTH_METHOD"] == "service_account"


def test_temp_env_restores_absent_key(monkeypatch):
    from sample_ai_api_unified import state

    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
    with state.temp_env(EMBEDDING_MODEL_NAME="gemini-embedding-2"):
        assert os.environ["EMBEDDING_MODEL_NAME"] == "gemini-embedding-2"
    assert "EMBEDDING_MODEL_NAME" not in os.environ


def test_temp_env_restores_on_exception(monkeypatch):
    from sample_ai_api_unified import state

    monkeypatch.setenv("GOOGLE_AUTH_METHOD", "service_account")
    with pytest.raises(RuntimeError):
        with state.temp_env(GOOGLE_AUTH_METHOD="api_key"):
            raise RuntimeError("boom")
    assert os.environ["GOOGLE_AUTH_METHOD"] == "service_account"  # restored on error


async def test_videos_display_resolves_stale_model_without_writing(offline_env, monkeypatch):
    """Mounting the Videos screen shows the model the next call will use (a stale
    Vertex-only name resolves to the Developer-API default) but must not persist
    on a mount."""
    from sample_ai_api_unified import state

    monkeypatch.setenv("VIDEO_ENGINE", "google-gemini")
    monkeypatch.setenv("VIDEO_MODEL_NAME", "veo-3.0-fast-generate-001")  # Vertex-only, 404s
    writes: list = []
    monkeypatch.setattr(state, "set_model", lambda cap, model: writes.append((cap, model)))

    async with SampleApp().run_test(size=(120, 44)) as pilot:
        pilot.app.show_screen("videos")
        await pilot.pause()
        line = str(pilot.app.query_one("VideosScreen").query_one("#engine-line", Static).renderable)
        assert "veo-3.1-lite-generate-preview" in line  # the resolved Developer-API default
        assert writes == []  # a mere mount persisted nothing


async def test_related_rank_needs_a_seed(offline_env):
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        pilot.app.show_screen("embeddings")
        await pilot.pause()
        screen = pilot.app.query_one("EmbeddingsScreen")
        await pilot.click("#related")
        await pilot.pause()
        assert "Enter a phrase" in str(screen.query_one("#result", Static).renderable)


async def test_related_rank_gates_on_completions(offline_env, monkeypatch):
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        pilot.app.show_screen("embeddings")
        await pilot.pause()
        screen = pilot.app.query_one("EmbeddingsScreen")
        screen.query_one("#text", Input).value = "dogs like to sniff things"
        monkeypatch.delenv("COMPLETIONS_ENGINE", raising=False)  # generation unavailable
        await pilot.click("#related")
        await pilot.pause()
        assert "Completions engine not configured" in str(
            screen.query_one("#result", Static).renderable
        )


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


async def test_completions_stream_renders_chunks_live(offline_env, monkeypatch):
    import ai_api_unified

    from sample_ai_api_unified import middleware_profile as mp

    # PII disabled so streaming is allowed.
    monkeypatch.setattr(mp, "read_profile", lambda *a, **k: mp.MiddlewareProfile())

    class _FakeStreamingClient:
        # A chunk with Rich-markup-like brackets ([/INST]) must render literally,
        # not abort the stream with a MarkupError.
        def send_prompt_streaming(self, prompt, *, other_params=None):
            return iter(["Use the ", "[/INST] ", "token."])

    monkeypatch.setattr(
        ai_api_unified.AIFactory,
        "get_ai_completions_client",
        staticmethod(lambda: _FakeStreamingClient()),
    )

    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen._stream("what does [/INST] mean?")  # bracketed prompt echo too
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        # _last_result is the markup-resolved plain text (what the user sees and
        # can copy); the brackets survive because the text was escaped.
        result = screen._last_result
        assert "Use the [/INST] token." in result  # chunks accumulated, brackets intact
        assert "what does [/INST] mean?" in result  # prompt echo intact
        assert "streamed 3 chunks" in result  # completion summary


async def test_completions_stream_button_is_wired(offline_env, monkeypatch):
    """Clicking Stream reaches the handler (guards the @on wiring)."""
    import ai_api_unified

    from sample_ai_api_unified import middleware_profile as mp

    monkeypatch.setattr(mp, "read_profile", lambda *a, **k: mp.MiddlewareProfile())

    class _FakeStreamingClient:
        def send_prompt_streaming(self, prompt, *, other_params=None):
            return iter(["ok"])

    monkeypatch.setattr(
        ai_api_unified.AIFactory,
        "get_ai_completions_client",
        staticmethod(lambda: _FakeStreamingClient()),
    )
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        await pilot.pause()  # let the layout settle so the click hit-tests
        screen = pilot.app.query_one("CompletionsScreen")
        screen.query_one("#prompt", Input).value = "hi"
        await pilot.click("#stream")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "streamed 1 chunks" in str(screen.query_one("#result", Static).renderable)


async def test_completions_stream_blocked_when_pii_enabled(offline_env, monkeypatch):
    from sample_ai_api_unified import middleware_profile as mp

    monkeypatch.setattr(
        mp, "read_profile", lambda *a, **k: mp.MiddlewareProfile(pii=mp.PiiProfile(enabled=True))
    )
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen._stream("hi")
        await pilot.pause()
        result = str(screen.query_one("#result", Static).renderable)
        assert "PII redaction" in result and "Middleware screen" in result


async def test_completions_stream_empty_prompt_warns(offline_env):
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen._stream("")
        await pilot.pause()
        assert "Enter a prompt" in str(screen.query_one("#result", Static).renderable)


async def test_completions_stream_error_is_shown_not_fatal(offline_env, monkeypatch):
    import ai_api_unified

    from sample_ai_api_unified import middleware_profile as mp

    monkeypatch.setattr(mp, "read_profile", lambda *a, **k: mp.MiddlewareProfile())

    class _BoomClient:
        def send_prompt_streaming(self, prompt, *, other_params=None):
            def gen():
                yield "partial "
                raise RuntimeError("stream broke")

            return gen()

    monkeypatch.setattr(
        ai_api_unified.AIFactory,
        "get_ai_completions_client",
        staticmethod(lambda: _BoomClient()),
    )
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen._stream("hi")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        result = str(screen.query_one("#result", Static).renderable)
        assert "RuntimeError" in result and "stream broke" in result
        assert pilot.app.query("CompletionsScreen")  # app still alive


import ai_api_unified as _aiu  # noqa: E402

# Batch completions need ai-api-unified 2.13.0+; CI installs the base library
# from PyPI (2.11.0), so skip these there. They run against a local checkout.
requires_batch = pytest.mark.skipif(
    not hasattr(_aiu, "AIBatchRequestItem"),
    reason="batch API requires ai-api-unified 2.13.0+",
)


@requires_batch
async def test_batch_gated_on_capability(offline_env, monkeypatch):
    import ai_api_unified

    class _NoBatch:
        model_name = "gpt-4o-mini"

        class capabilities:  # noqa: N801 - mirrors the client attribute
            supports_batch = False

    monkeypatch.setattr(
        ai_api_unified.AIFactory, "get_ai_completions_client", staticmethod(lambda: _NoBatch())
    )
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen._on_batch()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "does not support batch" in screen._last_result


@requires_batch
async def test_batch_submits_polls_and_renders_results(offline_env, monkeypatch):
    import ai_api_unified
    from ai_api_unified import (
        AIBatchItemStatus,
        AIBatchJob,
        AIBatchResultItem,
        AIBatchStatus,
    )

    from sample_ai_api_unified.tui.screens import completions as comp

    monkeypatch.setattr(comp, "BATCH_POLL_SECONDS", 0)  # don't sleep in the test

    class _Batch:
        model_name = "claude-opus-4-8"

        class capabilities:  # noqa: N801
            supports_batch = True

        def __init__(self):
            self._items = []
            self._polls = 0

        def submit_batch(self, items):
            self._items = items
            return AIBatchJob(
                batch_id="claude:b1",
                provider_batch_id="b1",
                status=AIBatchStatus.IN_PROGRESS,
                request_count=len(items),
                processing_count=len(items),
            )

        def get_batch(self, job):  # ends on the first poll
            self._polls += 1
            return job.model_copy(
                update={
                    "status": AIBatchStatus.ENDED,
                    "processing_count": 0,
                    "succeeded_count": len(self._items),
                }
            )

        def get_batch_results(self, job):
            return [
                AIBatchResultItem(
                    custom_id=item.custom_id,
                    status=AIBatchItemStatus.SUCCEEDED,
                    text=f"answer for {item.custom_id}",
                    provider_prompt_tokens=8,
                    provider_completion_tokens=4,
                )
                for item in self._items
            ]

    monkeypatch.setattr(
        ai_api_unified.AIFactory, "get_ai_completions_client", staticmethod(lambda: _Batch())
    )
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen._on_batch()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        result = screen._last_result
        assert "q1" in result and "answer for q1" in result  # correlated by custom_id
        assert "succeeded" in result and "claude:b1" in result


async def test_completions_send_renders_bracketed_reply(offline_env, monkeypatch):
    """A non-streaming reply with bracket tokens must render literally, not crash."""
    import ai_api_unified

    class _FakeClient:
        def send_prompt(self, prompt, *, other_params=None):
            return "code: [/foo] and [bold]x"

    monkeypatch.setattr(
        ai_api_unified.AIFactory,
        "get_ai_completions_client",
        staticmethod(lambda: _FakeClient()),
    )
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen._send("hi [/x]")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "[/foo]" in screen._last_result and "[bold]x" in screen._last_result
        assert pilot.app.query("CompletionsScreen")  # rendered without aborting


# The params classes import provider SDK modules that live behind optional
# extras; CI installs the base library only, so skip engines whose SDK is
# absent (same convention as test_catalog_registry_sync).
@pytest.mark.parametrize(
    "engine,sdk_module",
    [
        ("openai", "openai"),
        ("google-gemini", "google.genai"),
        ("claude", None),  # base params only — no provider SDK import
    ],
)
def test_prompt_params_cover_each_native_engine(engine, sdk_module):
    """System-prompt/image params exist for every engine whose library client
    honors them."""
    from sample_ai_api_unified.tui.screens.completions import _prompt_params

    if sdk_module is not None:
        pytest.importorskip(sdk_module)
    params = _prompt_params(engine, system_prompt="be terse")
    assert params is not None, f"{engine} should support system prompts"
    assert params.system_prompt == "be terse"


def test_prompt_params_unknown_engine_falls_back_to_none():
    from sample_ai_api_unified.tui.screens.completions import _prompt_params

    assert _prompt_params("some-custom-engine", system_prompt="x") is None


async def test_count_tokens_gates_on_capability(offline_env, monkeypatch):
    """Non-supporting providers get a message; supporting ones get a count."""
    import ai_api_unified

    class _NoCount:
        model_name = "gpt-4o-mini"

        class capabilities:  # noqa: N801 - mimics the client attribute
            supports_token_counting = False

    monkeypatch.setattr(
        ai_api_unified.AIFactory, "get_ai_completions_client", staticmethod(lambda: _NoCount())
    )
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen.query_one("#prompt", Input).value = "measure me"
        screen._on_count()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "does not support provider-side token counting" in screen._last_result

    class _Counts:
        model_name = "amazon.nova-lite-v1:0"

        class capabilities:  # noqa: N801
            supports_token_counting = True

        def count_tokens(self, prompt, *, other_params=None):
            return 42

    monkeypatch.setattr(
        ai_api_unified.AIFactory, "get_ai_completions_client", staticmethod(lambda: _Counts())
    )
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen.query_one("#prompt", Input).value = "measure me"
        screen._on_count()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "42" in screen._last_result and "input tokens" in screen._last_result


async def test_model_info_shows_structured_pricing_and_lifecycle(offline_env, monkeypatch):
    """Model info renders the 2.9.0 split rates, example cost, and lifecycle."""
    import ai_api_unified

    class _Client:
        model_name = "gpt-4o-mini"
        max_context_tokens = 128_000

        @property
        def capabilities(self):
            from ai_api_unified.pricing import get_model_pricing

            class Caps:
                pricing = get_model_pricing("openai", "gpt-4o-mini")

            return Caps()

        def compute_completion_cost(self, *, input_tokens, output_tokens=0, cached_input_tokens=0):
            return 0.00045

    monkeypatch.setattr(
        ai_api_unified.AIFactory, "get_ai_completions_client", staticmethod(lambda: _Client())
    )
    monkeypatch.setattr(
        ai_api_unified.AIFactory, "list_completion_models", staticmethod(lambda c: ["gpt-4o-mini"])
    )
    monkeypatch.setenv("COMPLETIONS_ENGINE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    async with SampleApp().run_test() as pilot:
        screen = pilot.app.query_one("CompletionsScreen")
        screen._on_info()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        result = screen._last_result
        assert "per 1M tokens" in result and "input $" in result  # split rates
        assert "compute_completion_cost" in result  # example cost line
        assert "Lifecycle: active" in result  # registry lifecycle status


async def test_middleware_emit_cost_switch_persists(offline_env, monkeypatch, tmp_path):
    from sample_ai_api_unified import middleware_profile as mp

    yaml_path = tmp_path / "middleware.yaml"
    monkeypatch.setattr(mp.paths, "MIDDLEWARE_YAML_PATH", yaml_path)
    monkeypatch.setattr(mp.envfile, "set_env_values", lambda values: None)

    async with SampleApp().run_test(size=(120, 50)) as pilot:
        pilot.app.show_screen("middleware")
        await pilot.pause()
        await pilot.pause()  # let autosave arm
        screen = pilot.app.query_one("MiddlewareScreen")
        from textual.widgets import Select, Switch

        # The new switch must not push other controls off a 120-col terminal:
        # the log-level Select stays fully inside the viewport.
        log_level = screen.query_one("#obs-log-level", Select)
        assert log_level.region.right <= pilot.app.size.width
        screen.query_one("#obs-emit-cost", Switch).value = True
        await pilot.pause()
        assert mp.read_profile(yaml_path).observability.emit_cost is True


async def test_providers_tables_populate(offline_env):
    from sample_ai_api_unified import catalog

    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen("providers")
        await pilot.pause()
        config = pilot.app.query_one("#config-table", DataTable)
        status = pilot.app.query_one("#status-table", DataTable)
        assert config.row_count == 5  # five capabilities
        # One status row per provider in the catalog (openai, anthropic,
        # google, aws, azure, elevenlabs, ...) — derive, don't hardcode.
        assert status.row_count == len(catalog.PROVIDERS)


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


@pytest.mark.parametrize(
    "key,screen_cls,input_id,expected_kind",
    [
        ("completions", "CompletionsScreen", "#prompt", "completion"),
        ("images", "ImagesScreen", "#prompt", "image"),
        ("videos", "VideosScreen", "#prompt", "video"),
        ("voice", "VoiceScreen", "#text", "tts"),
    ],
)
async def test_generate_prompt_fills_input(
    offline_env, monkeypatch, key, screen_cls, input_id, expected_kind
):
    """The 'Generate prompt' button fills the input via the (stubbed) API."""
    from sample_ai_api_unified import promptgen

    seen = {}

    def fake_generate(kind: str) -> str:
        seen["kind"] = kind
        return f"generated for {kind}"

    monkeypatch.setattr(promptgen, "generate_prompt", fake_generate)
    monkeypatch.setenv("IMAGE_ENGINE", "google-gemini")
    monkeypatch.setenv("VIDEO_ENGINE", "google-gemini")
    monkeypatch.setenv("AI_VOICE_ENGINE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    async with SampleApp().run_test(size=(140, 44)) as pilot:
        pilot.app.show_screen(key)
        await pilot.pause()
        screen = pilot.app.query_one(screen_cls)
        await pilot.click("#gen-prompt" if key != "completions" else "#generate")
        for _ in range(40):
            await pilot.pause(0.05)
            if screen.query_one(input_id, Input).value:
                break
        assert seen["kind"] == expected_kind
        assert screen.query_one(input_id, Input).value == f"generated for {expected_kind}"


async def test_multimodal_no_silent_engine_switch(offline_env, monkeypatch):
    """Clicking Multimodal without google configured must not rewrite .env."""
    from sample_ai_api_unified.tui.screens import embeddings as emb

    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_AUTH_METHOD", "api_key")
    monkeypatch.setenv("EMBEDDING_ENGINE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    called = {}
    monkeypatch.setattr(
        emb.state, "set_engine", lambda *a, **k: called.setdefault("switched", True)
    )

    async with SampleApp().run_test(size=(140, 44)) as pilot:
        pilot.app.show_screen("embeddings")
        await pilot.pause()
        screen = pilot.app.query_one("EmbeddingsScreen")
        await pilot.click("#multimodal")
        await pilot.pause()
        assert "google-gemini configured" in str(screen.query_one("#result", Static).renderable)
        assert "switched" not in called  # engine was not changed


async def test_generate_prompt_needs_completions(offline_env, monkeypatch):
    """Generation gates on the completions engine, not the screen's own engine."""
    monkeypatch.delenv("COMPLETIONS_ENGINE", raising=False)
    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen("completions")
        await pilot.pause()
        screen = pilot.app.query_one("CompletionsScreen")
        await pilot.click("#generate")
        await pilot.pause()
        assert "not configured" in str(screen.query_one("#result", Static).renderable)


async def test_structured_shows_full_prompt(offline_env, monkeypatch):
    """The structured screen must surface the exact strict_schema_prompt text."""

    captured = {}

    class FakeResult:
        def model_dump(self, exclude=None):
            return {"name": "Ada"}

    class FakeClient:
        def strict_schema_prompt(self, *, prompt, response_model, max_response_tokens):
            captured["prompt"] = prompt
            return FakeResult()

    import ai_api_unified

    monkeypatch.setattr(
        ai_api_unified.AIFactory, "get_ai_completions_client", staticmethod(lambda: FakeClient())
    )

    async with SampleApp().run_test() as pilot:
        pilot.app.show_screen("structured")
        await pilot.pause()
        screen = pilot.app.query_one("StructuredScreen")
        await pilot.click("#contact")
        rendered = ""
        for _ in range(40):
            await pilot.pause(0.05)
            rendered = str(screen.query_one("#result", Static).renderable)
            if "Prompt:" in rendered:
                break
        # the exact prompt sent is shown, and it is the schema's get_prompt()
        assert "Prompt:" in rendered
        assert captured["prompt"] in rendered
        assert "Extract the person's name" in rendered


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
