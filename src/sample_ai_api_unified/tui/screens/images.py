"""Image generation screen: prompt in, PNG saved to disk (and opened)."""

from __future__ import annotations

import time

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ... import paths, samples, state
from ..fileutil import open_file
from ..modals import ChoiceModal
from .base import CapabilityScreen

CAPABILITY = "images"


def _default_properties(engine: str):
    if engine == "google-gemini":
        from ai_api_unified.images.ai_google_gemini_images import AIGoogleGeminiImageProperties

        return AIGoogleGeminiImageProperties(aspect_ratio="1:1")
    if engine == "openai":
        from ai_api_unified.images.ai_openai_images import AIOpenAIImageProperties

        return AIOpenAIImageProperties(width=1024, height=1024)
    if engine in ("nova-canvas", "nova", "bedrock"):
        from ai_api_unified.images.ai_bedrock_images import AINovaCanvasImageProperties

        return AINovaCanvasImageProperties()
    from ai_api_unified import AIBaseImageProperties

    return AIBaseImageProperties(width=1024, height=1024)


class ImagesScreen(CapabilityScreen):
    title_text = "Image generation"
    subtitle_text = "Generate an image; it is saved to generated_images/ and opened."

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        yield Input(placeholder="Image prompt…", id="prompt")
        with Horizontal(classes="actions"):
            yield Button("Generate", variant="primary", id="generate")
            yield Button("Sample prompt", id="sample")
        yield Static("", classes="result-panel", id="result")

    def on_mount(self) -> None:
        engine = state.current_engine(CAPABILITY) or "unset"
        model = state.current_model(CAPABILITY) or "provider default"
        self.query_one("#engine-line", Static).update(f"engine: {engine}   model: {model}")

    def _generate(self, prompt: str) -> None:
        if not prompt.strip():
            self.set_result("result", "[yellow]Enter a prompt first.[/yellow]")
            return
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return
        engine = state.current_engine(CAPABILITY)

        def call() -> str:
            from ai_api_unified import AIFactory

            properties = _default_properties(engine)
            client = AIFactory.get_ai_images_client()
            images = client.generate_images(prompt, properties)
            paths.IMAGES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            saved = []
            for index, image_bytes in enumerate(images):
                out_path = paths.IMAGES_OUTPUT_DIR / f"image_{stamp}_{index}.png"
                out_path.write_bytes(image_bytes)
                saved.append(out_path)
            for out_path in saved:
                open_file(out_path)
            return "Saved:\n" + "\n".join(str(p) for p in saved)

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Generating image via {engine}",
        )

    @on(Button.Pressed, "#generate")
    def _on_generate(self) -> None:
        self._generate(self.query_one("#prompt", Input).value)

    @on(Input.Submitted, "#prompt")
    def _on_submit(self) -> None:
        self._generate(self.query_one("#prompt", Input).value)

    @on(Button.Pressed, "#sample")
    def _on_sample(self) -> None:
        options = [(text, text) for text in samples.IMAGE_GEN_PROMPTS]

        def chosen(prompt: str | None) -> None:
            if prompt:
                self.query_one("#prompt", Input).value = prompt
                self._generate(prompt)

        self.app.push_screen(ChoiceModal("Pick a prompt", options), chosen)
