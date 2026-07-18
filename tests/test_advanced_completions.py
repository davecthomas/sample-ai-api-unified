"""PR2 advanced-completions tests: send_structured_output, retry policy, and the
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
    def __init__(self, structured=True):
        self.supports_structured_output = structured


class _Client:
    def __init__(self, *, result=None, caps=None, error=None):
        self._result = result
        self.capabilities = caps or _Caps()
        self.model_name = "fake-model"
        self._error = error

    def send_structured_output(self, *, prompt=None, response_model=None, max_response_tokens=2048):
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
