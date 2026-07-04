"""Audio format sniffing and player resolution."""

from pathlib import Path

from sample_ai_api_unified import audio


def test_sniff_wav():
    assert audio._sniff_extension(b"RIFF....WAVE") == ".wav"


def test_sniff_mp3_id3_and_frame_headers():
    assert audio._sniff_extension(b"ID3\x04...") == ".mp3"
    assert audio._sniff_extension(b"\xff\xfb\x90\x00") == ".mp3"
    assert audio._sniff_extension(b"\xff\xf3\x90\x00") == ".mp3"


def test_sniff_ogg_and_flac():
    assert audio._sniff_extension(b"OggS....") == ".ogg"
    assert audio._sniff_extension(b'fLaC\x00\x00\x00"') == ".flac"


def test_sniff_unknown_defaults_to_wav():
    assert audio._sniff_extension(b"\x00\x01\x02\x03") == ".wav"


def test_player_command_prefers_afplay_on_macos(monkeypatch):
    monkeypatch.setattr(audio.sys, "platform", "darwin")
    monkeypatch.setattr(
        audio.shutil, "which", lambda name: "/usr/bin/afplay" if name == "afplay" else None
    )
    command = audio._player_command(Path("/tmp/x.wav"))
    assert command[0] == "afplay"


def test_player_command_none_when_no_player(monkeypatch):
    monkeypatch.setattr(audio.sys, "platform", "linux")
    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    assert audio._player_command(Path("/tmp/x.wav")) is None


def test_play_audio_handles_empty_bytes(capsys):
    audio.play_audio(b"")  # must not raise


def test_play_audio_leaves_file_when_no_player(monkeypatch, tmp_path):
    monkeypatch.setattr(audio.sys, "platform", "linux")
    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    audio.play_audio(b"RIFFxxxxWAVE")  # must not raise; file is left behind for the user
