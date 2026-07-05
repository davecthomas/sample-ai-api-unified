"""System-clipboard helper: command selection and subprocess handling."""

import subprocess

from sample_ai_api_unified import clipboard


def test_macos_prefers_pbcopy(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "darwin")
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: "/usr/bin/pbcopy")
    assert clipboard._clipboard_command() == ["pbcopy"]


def test_linux_falls_back_to_xclip(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: name if name == "xclip" else None)
    assert clipboard._clipboard_command() == ["xclip", "-selection", "clipboard"]


def test_no_tool_returns_none_and_copy_reports_false(monkeypatch):
    monkeypatch.setattr(clipboard.sys, "platform", "linux")
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: None)
    assert clipboard._clipboard_command() is None
    assert clipboard.copy_to_clipboard("hello") is False


def test_copy_pipes_text_to_the_command(monkeypatch):
    seen = {}

    def fake_run(command, input, check):  # noqa: A002 - mirrors subprocess.run
        seen["command"] = command
        seen["input"] = input
        seen["check"] = check
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(clipboard, "_clipboard_command", lambda: ["pbcopy"])
    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    assert clipboard.copy_to_clipboard("RuntimeError: 404") is True
    assert seen["command"] == ["pbcopy"]
    assert seen["input"] == b"RuntimeError: 404"
    assert seen["check"] is True


def test_copy_returns_false_when_command_fails(monkeypatch):
    def fake_run(command, input, check):  # noqa: A002
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(clipboard, "_clipboard_command", lambda: ["pbcopy"])
    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    assert clipboard.copy_to_clipboard("x") is False
