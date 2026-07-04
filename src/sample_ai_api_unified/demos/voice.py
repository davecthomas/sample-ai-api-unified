"""Voice demos: TTS through the speakers (play only) and an STT roundtrip."""

from __future__ import annotations

from .. import audio, runner, samples, state, ui
from ..guard import provider_errors

CAPABILITY = "voice"
VOICES_PER_PAGE = 24


def voice_client():
    import os

    from ai_api_unified import AIVoiceFactory

    client = AIVoiceFactory.create()
    # ai-api-unified 2.6.0: AIVoiceOpenAI.text_to_voice reads self.user but the
    # class never defines that field, so every call raises AttributeError.
    # Bypass pydantic's field check until the library ships a fix.
    if not hasattr(client, "user"):
        object.__setattr__(client, "user", os.environ.get("OPENAI_USER", "sample-app"))
    return client


def _pick_voice(client) -> None:
    voices = client.get_available_voices()
    if not voices:
        ui.warn("This provider returned no voice list; the default voice will be used.")
        return
    english = [v for v in voices if (v.locale or "").startswith("en")] or voices
    page = 0
    while True:
        window = english[page * VOICES_PER_PAGE : (page + 1) * VOICES_PER_PAGE]
        options = [
            ui.MenuOption(
                f"{voice.voice_name}",
                voice,
                " ".join(part for part in (voice.locale, voice.gender) if part),
            )
            for voice in window
        ]
        if (page + 1) * VOICES_PER_PAGE < len(english):
            options.append(ui.MenuOption("More voices…", "more"))
        picked = ui.choose(
            f"Choose a voice ({len(english)} available)", options, back_label="Keep current"
        )
        if picked is None:
            return
        if picked.value == "more":
            page += 1
            continue
        client.selected_voice = picked.value
        ui.success(f"Voice set to {picked.value.voice_name}")
        return


def audio_format_for(client):
    if client.default_audio_format is not None:
        return client.default_audio_format
    formats = client.list_output_formats
    return formats[0] if formats else None


def _speak(text: str) -> None:
    if not state.ensure_capability_ready(CAPABILITY):
        return
    engine = state.current_engine(CAPABILITY)
    with provider_errors():
        client = voice_client()
        _pick_voice(client)
        voice = client.selected_voice
        voice_name = voice.voice_name if voice else "default"
        audio_bytes = runner.run_call(
            f"TTS via {engine} ({voice_name})",
            lambda: client.text_to_voice(
                text_to_convert=text, voice=voice, audio_format=audio_format_for(client)
            ),
        )
        audio.play_audio(audio_bytes)


def _stt_roundtrip() -> None:
    """Synthesize a sentence, then transcribe those bytes back to text."""
    if not state.ensure_capability_ready(CAPABILITY):
        return
    engine = state.current_engine(CAPABILITY)
    original = samples.TTS_SAMPLES[0]
    with provider_errors():
        client = voice_client()
        audio_bytes = runner.run_call(
            f"TTS via {engine}",
            lambda: client.text_to_voice(
                text_to_convert=original,
                voice=client.selected_voice,
                audio_format=audio_format_for(client),
            ),
        )
        audio.play_audio(audio_bytes)
        transcript = runner.run_call(
            f"STT via {engine}",
            lambda: client.speech_to_text(audio_bytes),
        )
        ui.info(f"Original:   {original}")
        ui.success(f"Transcript: {transcript}")


def run() -> None:
    while True:
        ui.header("Voice (TTS / STT)", f"engine: {state.current_engine(CAPABILITY) or 'unset'}")
        picked = ui.choose(
            "Voice demos",
            [
                ui.MenuOption("Speak a sample sentence", "sample", "pick voice, plays audio"),
                ui.MenuOption("Speak custom text", "custom"),
                ui.MenuOption(
                    "Speech-to-text roundtrip", "stt", "TTS then transcribe the audio back"
                ),
                ui.MenuOption("Switch voice provider", "engine"),
            ],
        )
        if picked is None:
            return
        if picked.value == "sample":
            text = ui.choose_value("Pick a sentence", list(samples.TTS_SAMPLES))
            if text:
                _speak(text)
        elif picked.value == "custom":
            text = ui.ask("Text to speak")
            if text:
                _speak(text)
        elif picked.value == "stt":
            _stt_roundtrip()
        elif picked.value == "engine":
            state.switch_engine_menu(CAPABILITY)
