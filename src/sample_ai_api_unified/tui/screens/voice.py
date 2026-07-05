"""Voice screen: TTS through the speakers with a voice picker, plus STT roundtrip."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ... import audio, samples, state
from ...voice_util import audio_format_for, voice_client
from ..modals import ChoiceModal
from .base import CapabilityScreen

CAPABILITY = "voice"


class VoiceScreen(CapabilityScreen):
    title_text = "Voice (TTS / STT)"
    subtitle_text = "Synthesize speech through your speakers; STT transcribes it back."

    # A fresh client is created per call, so the picked voice is remembered here
    # and re-applied to each client.
    _selected_voice = None

    def _new_client(self):
        client = voice_client()
        if self._selected_voice is not None:
            client.selected_voice = self._selected_voice
        return client

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        yield Input(placeholder="Text to speak…", id="text")
        with Horizontal(classes="actions"):
            yield Button("Speak", variant="primary", id="speak")
            yield Button("Sample sentence", id="sample")
            yield Button("Generate sentence", id="gen-prompt")
        with Horizontal(classes="actions"):
            yield Button("Pick voice", id="voice")
            yield Button("STT roundtrip", id="stt")
        yield Static("", classes="result-panel", id="result")

    def on_mount(self) -> None:
        engine = state.current_engine(CAPABILITY) or "unset"
        self.query_one("#engine-line", Static).update(f"engine: {engine}")

    def _ready(self) -> bool:
        if self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            return True
        self.set_result("result", "[yellow]Engine not configured.[/yellow]")
        return False

    def _speak(self, text: str) -> None:
        if not text.strip():
            self.set_result("result", "[yellow]Enter text first.[/yellow]")
            return
        if not self._ready():
            return
        engine = state.current_engine(CAPABILITY)

        def call() -> str:
            client = self._new_client()
            voice = client.selected_voice
            audio_bytes = client.text_to_voice(
                text_to_convert=text, voice=voice, audio_format=audio_format_for(client)
            )
            audio.play_audio(audio_bytes)
            name = voice.voice_name if voice else "default"
            return f"Spoken:\n{text}\n\nPlayed {len(audio_bytes):,} bytes via {engine} ({name})."

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"TTS via {engine}",
        )

    @on(Button.Pressed, "#speak")
    def _on_speak(self) -> None:
        self._speak(self.query_one("#text", Input).value)

    @on(Input.Submitted, "#text")
    def _on_submit(self) -> None:
        self._speak(self.query_one("#text", Input).value)

    @on(Button.Pressed, "#gen-prompt")
    def _on_gen_prompt(self) -> None:
        def fill(text: str) -> None:
            self.query_one("#text", Input).value = text
            self.set_result("result", f"Generated sentence (press Speak to hear it):\n\n{text}")

        self.generate_prompt("tts", fill)

    @on(Button.Pressed, "#sample")
    def _on_sample(self) -> None:
        options = [(text, text) for text in samples.TTS_SAMPLES]

        def chosen(text: str | None) -> None:
            if text:
                self.query_one("#text", Input).value = text
                self._speak(text)

        self.app.push_screen(ChoiceModal("Pick a sentence", options), chosen)

    @on(Button.Pressed, "#voice")
    def _on_pick_voice(self) -> None:
        if not self._ready():
            return

        def collect() -> list:
            client = self._new_client()
            voices = client.get_available_voices()
            english = [v for v in voices if (v.locale or "").startswith("en")] or voices
            return english

        def show(voices: list) -> None:
            if not voices:
                self.set_result("result", "[yellow]This provider returned no voice list.[/yellow]")
                return
            options = [
                (f"{v.voice_name} {v.locale or ''} {v.gender or ''}".strip(), v) for v in voices
            ]

            def chosen(voice) -> None:
                if voice is not None:
                    self._selected_voice = voice
                    self.set_result("result", f"Voice set to {voice.voice_name}.")

            self.app.push_screen(ChoiceModal("Choose a voice", options), chosen)

        self.run_blocking(collect, on_success=show, description="Loading voices")

    @on(Button.Pressed, "#stt")
    def _on_stt(self) -> None:
        if not self._ready():
            return
        original = samples.TTS_SAMPLES[0]
        engine = state.current_engine(CAPABILITY)

        def call() -> str:
            client = self._new_client()
            audio_bytes = client.text_to_voice(
                text_to_convert=original,
                voice=client.selected_voice,
                audio_format=audio_format_for(client),
            )
            audio.play_audio(audio_bytes)
            transcript = client.speech_to_text(audio_bytes)
            return f"Original:   {original}\nTranscript: {transcript}"

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"STT roundtrip via {engine}",
        )
