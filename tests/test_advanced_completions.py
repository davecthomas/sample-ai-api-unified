"""PR2 advanced-completions tests: send_structured_output (sync and async), the
async send_prompt variant, per-call timeouts, the retry policy, and the
AiProviderRequestError status_code surfaced in errors. All offline."""

import json

import pytest

pytest.importorskip("ai_api_unified")

import ai_api_unified as aiu  # noqa: E402
from textual.widgets import Static  # noqa: E402

from sample_ai_api_unified.tui.app import SampleApp  # noqa: E402

# offline_env comes from tests/conftest.py.


def _structured_result(data, finish="complete"):
    return aiu.AIStructuredOutputResult(
        data=data,
        finish_reason=aiu.AIFinishReason(finish),
        usage=aiu.AITokenUsage(
            input_tokens=20, output_tokens=8, cached_input_tokens=0, total_tokens=28
        ),
        raw_text=json.dumps(data) if data is not None else "",
    )


class _Caps:
    def __init__(self, structured=True, async_=True):
        self.supports_structured_output = structured
        self.supports_async = async_


class _Client:
    def __init__(self, *, result=None, caps=None, error=None):
        self._result = result
        self.capabilities = caps or _Caps()
        self.model_name = "fake-model"
        self._error = error
        self.calls: list[dict] = []

    def send_structured_output(self, **kwargs):
        self.calls.append({"method": "send_structured_output", **kwargs})
        if self._error is not None:
            raise self._error
        return self._result

    async def asend_structured_output(self, **kwargs):
        self.calls.append({"method": "asend_structured_output", **kwargs})
        if self._error is not None:
            raise self._error
        return self._result


def _rendered(screen):
    return str(screen.query_one("#result", Static).renderable)


async def _structured(pilot):
    pilot.app.show_screen("structured")
    await pilot.pause()
    return pilot.app.query_one("StructuredScreen")


async def test_structured_output_renders_data_and_usage(offline_env, monkeypatch):
    client = _Client(result=_structured_result({"name": "Ada Byron", "city": "Lisbon"}))
    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _structured(pilot)
        await pilot.click("#structured-output")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        out = _rendered(screen)
        assert "finish_reason=complete" in out
        assert "20 in / 8 out" in out
        assert "Ada Byron" in out and "Lisbon" in out


async def test_structured_output_gated_when_unsupported(offline_env, monkeypatch):
    client = _Client(caps=_Caps(structured=False))
    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _structured(pilot)
        await pilot.click("#structured-output")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "supports_structured_output" in _rendered(screen)


async def test_provider_request_error_status_code_shown(offline_env, monkeypatch):
    class _Boom(Exception):
        status_code = 429

    client = _Client(error=_Boom("rate limited"))
    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _structured(pilot)
        await pilot.click("#structured-output")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        out = _rendered(screen)
        assert "status_code=429" in out and "rate limited" in out


async def test_structured_output_async_variant(offline_env, monkeypatch):
    client = _Client(result=_structured_result({"name": "Grace Hopper", "city": "Oslo"}))
    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _structured(pilot)
        await pilot.click("#structured-async")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        out = _rendered(screen)
        assert "asend_structured_output" in out and "Grace Hopper" in out
        assert client.calls[0]["method"] == "asend_structured_output"
        # The async demo carries a per-call deadline (library 2.14).
        assert client.calls[0]["request_timeout_seconds"] > 0


async def test_structured_output_async_gated_when_no_async_client(offline_env, monkeypatch):
    client = _Client(caps=_Caps(async_=False))
    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _structured(pilot)
        await pilot.click("#structured-async")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "supports_async" in _rendered(screen)
        assert client.calls == []


async def test_capability_error_renders_as_a_capability_note(offline_env, monkeypatch):
    """The typed gap error reads yellow with the gate named, not as a red failure."""
    client = _Client(
        error=aiu.AiProviderCapabilityUnsupportedError("structured output is not implemented here")
    )
    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _structured(pilot)
        await pilot.click("#structured-output")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        out = _rendered(screen)
        assert "[yellow]" in out and "[red]" not in out
        assert "capability gate" in out and "not implemented here" in out


class _CompletionsClient:
    def __init__(self, *, reply="hello there", async_=True, error=None):
        self._reply = reply
        self._error = error
        self.capabilities = _Caps(async_=async_)
        self.model_name = "fake-model"
        self.calls: list[dict] = []

    def send_prompt(self, prompt, **kwargs):
        self.calls.append({"method": "send_prompt", "prompt": prompt, **kwargs})
        if self._error is not None:
            raise self._error
        return self._reply

    async def asend_prompt(self, prompt, **kwargs):
        self.calls.append({"method": "asend_prompt", "prompt": prompt, **kwargs})
        if self._error is not None:
            raise self._error
        return self._reply


async def _completions(pilot, prompt="Explain a Merkle tree."):
    from textual.widgets import Input

    pilot.app.show_screen("completions")
    await pilot.pause()
    screen = pilot.app.query_one("CompletionsScreen")
    screen.query_one("#prompt", Input).value = prompt
    return screen


async def test_async_send_awaits_asend_prompt(offline_env, monkeypatch):
    client = _CompletionsClient(reply="awaited reply")
    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _completions(pilot)
        await pilot.click("#async")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        out = _rendered(screen)
        assert "awaited reply" in out and "asend_prompt" in out
        assert client.calls[0]["method"] == "asend_prompt"


async def test_async_send_gated_when_no_async_client(offline_env, monkeypatch):
    client = _CompletionsClient(async_=False)
    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _completions(pilot)
        await pilot.click("#async")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert "supports_async" in _rendered(screen)
        assert client.calls == []


async def test_per_call_timeout_passes_request_timeout_seconds(offline_env, monkeypatch):
    from sample_ai_api_unified.tui.screens.completions import TIMEOUT_CHOICES

    client = _CompletionsClient(reply="fast enough")
    monkeypatch.setattr(aiu.AIFactory, "get_ai_completions_client", staticmethod(lambda: client))
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        screen = await _completions(pilot)
        await pilot.click("#timeout")
        await pilot.pause()
        await pilot.press("enter")  # first option in the modal
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        expected = TIMEOUT_CHOICES[0][1]
        assert client.calls[0]["request_timeout_seconds"] == expected
        out = _rendered(screen)
        assert f"request_timeout_seconds={expected}" in out and "fast enough" in out


async def test_retry_policy_selector_persists(offline_env, monkeypatch):
    from sample_ai_api_unified import envfile

    captured = {}

    def fake_set(values):
        captured.update(values)
        for key, value in values.items():
            monkeypatch.setenv(key, value)

    monkeypatch.setattr(envfile, "set_env_values", fake_set)
    async with SampleApp().run_test(size=(120, 44)) as pilot:
        pilot.app.show_screen("providers")
        await pilot.pause()
        screen = pilot.app.query_one("ProvidersScreen")
        # Default before any change.
        assert "retry policy: default" in str(screen.query_one("#retry-line", Static).renderable)
        await pilot.click("#retry")
        await pilot.pause()
        await pilot.press("down")  # move off "default (current)" to "none"
        await pilot.press("enter")
        await pilot.pause()
        assert captured.get("COMPLETIONS_RETRY_POLICY") == "none"
        assert "retry policy: none" in str(screen.query_one("#retry-line", Static).renderable)
