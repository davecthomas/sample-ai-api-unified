"""Menu parsing: numbered selection, invalid input retry, back, toggles."""

import pytest

from sample_ai_api_unified import ui


def feed(monkeypatch, lines):
    iterator = iter(lines)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(iterator))


OPTIONS = [ui.MenuOption("Alpha", "a"), ui.MenuOption("Beta", "b")]


def test_choose_returns_selected_option(monkeypatch):
    feed(monkeypatch, ["2"])
    picked = ui.choose("t", OPTIONS)
    assert picked is not None and picked.value == "b"


def test_choose_zero_means_back(monkeypatch):
    feed(monkeypatch, ["0"])
    assert ui.choose("t", OPTIONS) is None


def test_choose_retries_on_invalid(monkeypatch):
    feed(monkeypatch, ["9", "nope", "1"])
    picked = ui.choose("t", OPTIONS)
    assert picked is not None and picked.value == "a"


def test_choose_exits_cleanly_on_eof(monkeypatch):
    def raise_eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    with pytest.raises(SystemExit):
        ui.choose("t", OPTIONS)


def test_ask_default(monkeypatch):
    feed(monkeypatch, [""])
    assert ui.ask("q", default="fallback") == "fallback"


def test_confirm_variants(monkeypatch):
    feed(monkeypatch, ["", "n", "YES"])
    assert ui.confirm("q", default=True) is True
    assert ui.confirm("q", default=True) is False
    assert ui.confirm("q", default=False) is True


def test_multi_toggle(monkeypatch):
    feed(monkeypatch, ["1", "2", "1", "0"])
    result = ui.multi_toggle("t", ["x", "y"], set())
    assert result == {"y"}
