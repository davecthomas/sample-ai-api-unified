"""provider_errors reports without crashing and passes through exits."""

import pytest

from sample_ai_api_unified.guard import provider_errors


def test_swallows_generic_exception():
    with provider_errors():
        raise RuntimeError("provider exploded")
    # reaching here proves the error was contained


def test_passes_through_system_exit():
    with pytest.raises(SystemExit):
        with provider_errors():
            raise SystemExit(3)


def test_passes_through_keyboard_interrupt():
    with pytest.raises(KeyboardInterrupt):
        with provider_errors():
            raise KeyboardInterrupt


def test_hint_for_dependency_error(capsys):
    error_class = type("AiProviderDependencyUnavailableError", (RuntimeError,), {})
    with provider_errors():
        raise error_class("no extra")
    output = capsys.readouterr().out
    assert "make setup-local" in output


def test_hint_for_missing_engine(capsys):
    with provider_errors():
        raise ValueError("COMPLETIONS_ENGINE must be configured explicitly")
    output = capsys.readouterr().out
    assert "Providers & models" in output
