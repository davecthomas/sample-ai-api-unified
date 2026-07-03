"""Image generation demos with per-provider property controls."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from .. import paths, runner, samples, state, ui
from ..guard import provider_errors

CAPABILITY = "images"


def _open_file(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        ui.info(f"Saved: {path}")


def _properties(engine: str):
    """Build image properties, offering the knobs each provider actually has."""
    if engine == "google-gemini":
        from ai_api_unified.images.ai_google_gemini_images import AIGoogleGeminiImageProperties

        aspect = ui.choose_value("Aspect ratio", ["1:1", "16:9", "9:16", "4:3", "3:4"])
        return AIGoogleGeminiImageProperties(aspect_ratio=aspect or "1:1")
    if engine == "openai":
        from ai_api_unified.images.ai_openai_images import AIOpenAIImageProperties

        size = ui.choose_value("Size", ["1024x1024", "1536x1024", "1024x1536"]) or "1024x1024"
        width, height = (int(part) for part in size.split("x"))
        return AIOpenAIImageProperties(width=width, height=height)
    if engine in ("nova-canvas", "nova", "bedrock"):
        from ai_api_unified.images.ai_bedrock_images import AINovaCanvasImageProperties

        return AINovaCanvasImageProperties()
    from ai_api_unified import AIBaseImageProperties

    return AIBaseImageProperties(width=1024, height=1024)


def _generate(prompt: str) -> None:
    if not state.ensure_capability_ready(CAPABILITY):
        return
    engine = state.current_engine(CAPABILITY)
    with provider_errors():
        from ai_api_unified import AIFactory

        properties = _properties(engine)
        client = AIFactory.get_ai_images_client()
        # Unlike the completions client, the images client exposes model_name
        # as a method rather than a property.
        model = client.model_name() if callable(client.model_name) else client.model_name
        ui.info(f"Model: {model}")
        images = runner.run_call(
            f"Generating image via {engine}",
            lambda: client.generate_images(prompt, properties),
        )
        paths.IMAGES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for index, image_bytes in enumerate(images):
            out_path = paths.IMAGES_OUTPUT_DIR / f"image_{stamp}_{index}.png"
            out_path.write_bytes(image_bytes)
            ui.success(f"Saved {len(image_bytes):,} bytes to {out_path}")
            _open_file(out_path)


def run() -> None:
    while True:
        ui.header(
            "Image generation",
            f"engine: {state.current_engine(CAPABILITY) or 'unset'}  "
            f"model: {state.current_model(CAPABILITY) or 'default'}",
        )
        picked = ui.choose(
            "Image generation demos",
            [
                ui.MenuOption("Generate from a sample prompt", "sample"),
                ui.MenuOption("Generate from a custom prompt", "custom"),
                ui.MenuOption("Switch engine", "engine"),
                ui.MenuOption("Switch model", "model"),
            ],
        )
        if picked is None:
            return
        if picked.value == "sample":
            prompt = ui.choose_value("Pick a prompt", list(samples.IMAGE_GEN_PROMPTS))
            if prompt:
                _generate(prompt)
        elif picked.value == "custom":
            prompt = ui.ask("Image prompt")
            if prompt:
                _generate(prompt)
        elif picked.value == "engine":
            state.switch_engine_menu(CAPABILITY)
        elif picked.value == "model":
            state.switch_model_menu(CAPABILITY)
