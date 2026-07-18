"""Conversation screen tests: chat turn, tool-use loop, and async — all offline.

A fake completions client returns real AITurnResult objects, so the screen's
rendering and the caller-owned tool loop are exercised without a network call.
"""

import pytest

pytest.importorskip("ai_api_unified")

import ai_api_unified as aiu  # noqa: E402
from textual.widgets import Input, Static  # noqa: E402

from sample_ai_api_unified.tui.app import SampleApp  # noqa: E402

# offline_env (COMPLETIONS_ENGINE configured, no I/O) comes from tests/conftest.py.


def _turn(text=None, tool_calls=None, finish="complete"):
    return aiu.AITurnResult(
        text=text,
        tool_calls=tool_calls or [],
        finish_reason=aiu.AIFinishReason(finish),
        raw_content={"role": "assistant"},
        usage=aiu.AITokenUsage(
            input_tokens=10, output_tokens=5, cached_input_tokens=0, total_tokens=15
        ),
    )


class _FakeCaps:
    def __init__(self, *, tool=True, async_=True):
        self.supports_tool_use = tool
        self.supports_async = async_


class _FakeClient:
    """Returns queued turns and records how the screen drove the loop."""

    def __init__(self, turns, caps):
        self._turns = list(turns)
        self.capabilities = caps
        self.model_name = "fake-model"
        self.sent = []
        self.built_results = []

    def send_conversation(self, system_prompt, messages, *, tools=None, **kwargs):
        self.sent.append({"system": system_prompt, "messages": list(messages), "tools": tools})
        return self._turns.pop(0)

    async def asend_conversation(self, system_prompt, messages, **kwargs):
        self.sent.append({"system": system_prompt, "messages": list(messages), "async": True})
        return self._turns.pop(0)

    def extend_messages_with_turn(self, messages, turn):
        messages.append({"role": "assistant", "content": turn.text or "", "_turn": True})
        return messages

    def build_tool_result_message(self, *, tool_call_id, result, is_error=False):
        message = {"role": "tool", "tool_call_id": tool_call_id, "result": result}
        self.built_results.append(message)
        return message


@pytest.fixture()
def install_client(monkeypatch):
    def install(turns, *, tool=True, async_=True):
        client = _FakeClient(turns, _FakeCaps(tool=tool, async_=async_))
        monkeypatch.setattr(
            aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client)
        )
        return client

    return install


async def _open(pilot):
    pilot.app.show_screen("conversation")
    await pilot.pause()
    return pilot.app.query_one("ConversationScreen")


def _rendered(screen) -> str:
    return str(screen.query_one("#result", Static).renderable)


async def test_send_turn_appends_transcript_and_usage(offline_env, install_client):
    client = install_client([_turn(text="A Merkle tree hashes pairs up to one root.")])
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#message", Input).value = "What is a Merkle tree?"
        await pilot.click("#send")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        out = _rendered(screen)
        assert "You:" in out and "What is a Merkle tree?" in out
        assert "Assistant:" in out and "hashes pairs up to one root" in out
        assert "finish=complete" in out and "10 in / 5 out" in out
        assert client.sent[0]["system"].startswith("You are a concise")


async def test_tool_use_loop_executes_and_feeds_result_back(offline_env, install_client):
    tool_call = aiu.AIToolCall(id="t1", name="lookup_ticket", input={"ticket_id": "VL-123"})
    client = install_client(
        [
            _turn(tool_calls=[tool_call], finish="tool_use"),
            _turn(text="Ticket VL-123 is in progress, assigned to Dana."),
        ],
        tool=True,
    )
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        await pilot.click("#tool")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        out = _rendered(screen)
        assert "tool call" in out and "lookup_ticket" in out
        assert "tool result" in out and "in progress" in out
        assert "Ticket VL-123 is in progress" in out
        # The caller-owned loop fed the executed tool result back to the model.
        assert client.built_results and client.built_results[0]["result"]["status"] == "in progress"


async def test_tool_use_gated_when_unsupported(offline_env, install_client):
    install_client([], tool=False)
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        await pilot.click("#tool")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "supports_tool_use" in _rendered(screen)


async def test_chat_turn_requires_tool_use_capability(offline_env, install_client):
    # send_conversation requires supports_tool_use even without tools, so plain
    # chat must gate on it too rather than surface a raw provider error.
    install_client([], tool=False)
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#message", Input).value = "hello"
        await pilot.click("#send")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "supports_tool_use" in _rendered(screen)
        assert screen._messages == []  # nothing committed on a gated turn


async def test_failed_turn_does_not_wedge_history(offline_env, monkeypatch):
    class _Boom:
        capabilities = _FakeCaps(tool=True)
        model_name = "fake-model"

        def send_conversation(self, *a, **k):
            raise RuntimeError("transient network error")

    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: _Boom()))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#message", Input).value = "hi"
        await pilot.click("#send")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        # The failed turn left no orphan user message to break the next turn.
        assert screen._messages == []
        assert "transient network error" in _rendered(screen)
        assert screen._busy is False


async def test_pii_middleware_blocks_conversation(offline_env, monkeypatch, install_client):
    from sample_ai_api_unified import middleware_profile as mp

    install_client([_turn(text="unused")])
    monkeypatch.setattr(
        mp, "read_profile", lambda *a, **k: mp.MiddlewareProfile(pii=mp.PiiProfile(enabled=True))
    )
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#message", Input).value = "hi"
        await pilot.click("#send")
        await pilot.pause()
        assert "PII redaction" in _rendered(screen)
        assert screen._messages == []


async def test_async_turn_runs_on_event_loop(offline_env, install_client):
    install_client([_turn(text="async reply here")], async_=True)
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#message", Input).value = "hello"
        await pilot.click("#async")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        out = _rendered(screen)
        assert "async reply here" in out and "event loop" in out


async def test_async_gated_when_unsupported(offline_env, install_client):
    install_client([], async_=False)
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#message", Input).value = "hello"
        await pilot.click("#async")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "no async client" in _rendered(screen)


async def test_conversation_gates_on_completions(offline_env, monkeypatch):
    monkeypatch.delenv("COMPLETIONS_ENGINE", raising=False)
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#message", Input).value = "hi"
        await pilot.click("#send")
        await pilot.pause()
        assert "not configured" in _rendered(screen)


async def test_reset_clears_history(offline_env, install_client):
    client = install_client([_turn(text="hi")])
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _open(pilot)
        screen.query_one("#message", Input).value = "hello"
        await pilot.click("#send")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert screen._messages  # a turn accumulated
        await pilot.click("#reset")
        await pilot.pause()
        assert screen._messages == []
        assert "cleared" in _rendered(screen).lower()
        assert client  # fake was used
