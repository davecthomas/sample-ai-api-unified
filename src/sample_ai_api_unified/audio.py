"""Play TTS audio through the speakers (play only — no file is kept)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


def _sniff_extension(audio: bytes) -> str:
    if audio[:4] == b"RIFF":
        return ".wav"
    if audio[:3] == b"ID3" or audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"
    if audio[:4] == b"OggS":
        return ".ogg"
    if audio[:4] == b"fLaC":
        return ".flac"
    return ".wav"


def _player_command(path: Path) -> list[str] | None:
    if sys.platform == "darwin" and shutil.which("afplay"):
        return ["afplay", str(path)]
    if shutil.which("ffplay"):
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
    if shutil.which("aplay") and path.suffix == ".wav":
        return ["aplay", "-q", str(path)]
    return None


def play_audio(audio: bytes) -> None:
    """Play audio through the OS default player; silent no-op if none is found."""
    if not audio:
        return
    suffix = _sniff_extension(audio)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(audio)
        temp_path = Path(handle.name)
    try:
        command = _player_command(temp_path)
        if command is None:
            _LOGGER.warning("No audio player found; audio left at %s", temp_path)
            return
        subprocess.run(command, check=False)
    finally:
        if _player_command(temp_path) is not None:
            temp_path.unlink(missing_ok=True)
