"""Model fallback (library 2.32): chain settings, route notes, and the demo — offline."""

import pytest

pytest.importorskip("ai_api_unified")

import ai_api_unified as aiu  # noqa: E402
from textual.widgets import Static  # noqa: E402

from sample_ai_api_unified import envfile, fallback  # noqa: E402
from sample_ai_api_unified.tui.app import SampleApp  # noqa: E402


class _RoutedClient:
    """Mimics AiFallbackCompletions' route introspection."""

    def __init__(self, served_index):
        self.candidates = [
            aiu.AIFallbackCandidate(engine="claude", model="claude-opus-5"),
            aiu.AIFallbackCandidate(engine="google-gemini", model="gemini-3.7-flash"),
        ]
        self.last_route = self.candidates[served_index]


def test_route_note_empty_for_plain_client_and_primary():
    assert fallback.route_note(object()) == ""
    assert fallback.route_note(_RoutedClient(0)) == ""


def test_route_note_names_the_fallback_that_served():
    note = fallback.route_note(_RoutedClient(1))
    assert "google-gemini:gemini-3.7-flash" in note
    assert "claude:claude-opus-5" in note


def test_set_and_clear_chain_round_trip(offline_env, monkeypatch):
    monkeypatch.delenv(fallback.FALLBACKS_ENV, raising=False)
    monkeypatch.delenv(fallback.FALLBACK_ON_ENV, raising=False)
    assert fallback.current_chain() == ""
    fallback.set_chain(fallback.GEMINI_FALLBACK, fallback.FALLBACK_ON_WITH_MODEL)
    assert envfile.get_env(fallback.FALLBACKS_ENV) == "google-gemini:gemini-3.7-flash"
    assert "model_unavailable" in fallback.current_fallback_on()
    fallback.clear_chain()
    assert fallback.current_chain() == ""
    assert fallback.current_fallback_on() == fallback.DEFAULT_FALLBACK_ON


def test_gemini_fallback_engine_is_registered():
    from ai_api_unified.ai_provider_registry import get_ai_provider_spec

    assert get_ai_provider_spec("completions", fallback.GEMINI_FALLBACK_ENGINE) is not None


async def test_failover_demo_shows_serving_candidate(offline_env, monkeypatch):
    calls = {}

    class _DemoClient:
        candidates = [
            aiu.AIFallbackCandidate(engine="google-gemini", model="no-such-model-failover-demo"),
            aiu.AIFallbackCandidate(engine="google-gemini", model="gemini-3.7-flash"),
        ]

        def send_conversation(self, system_prompt, messages, **kwargs):
            return aiu.AITurnResult(
                text="A Merkle tree hashes pairs up to one root.",
                tool_calls=[],
                finish_reason=aiu.AIFinishReason("complete"),
                raw_content={"role": "assistant"},
                usage=aiu.AITokenUsage(
                    input_tokens=10, output_tokens=5, cached_input_tokens=0, total_tokens=15
                ),
                provider_engine="google-gemini",
                model_name="gemini-3.7-flash",
            )

    def factory(**kwargs):
        calls.update(kwargs)
        return _DemoClient()

    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(factory))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        pilot.app.show_screen("conversation")
        await pilot.pause()
        screen = pilot.app.query_one("ConversationScreen")
        await pilot.click("#failover")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        out = str(screen.query_one("#result", Static).renderable)
    assert calls["model_name"] == "no-such-model-failover-demo"
    assert calls["fallbacks"] == [("google-gemini", "gemini-3.7-flash")]
    assert aiu.AiFallbackReason.MODEL_UNAVAILABLE in calls["fallback_on"]
    assert "served by google-gemini:gemini-3.7-flash" in out
    assert "hashes pairs up to one root" in out
