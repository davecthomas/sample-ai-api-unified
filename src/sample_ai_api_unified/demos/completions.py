"""Completions demos: prompts, system prompts, and image description."""

from __future__ import annotations

from pathlib import Path

from rich.panel import Panel

from .. import runner, samples, state, ui
from ..guard import provider_errors

CAPABILITY = "completions"


def _client():
    from ai_api_unified import AIFactory

    return AIFactory.get_ai_completions_client()


def _prompt_params(
    engine: str,
    *,
    system_prompt: str | None = None,
    image: bytes | None = None,
    mime_type: str = "image/png",
):
    """Build the provider-specific prompt params subclass, or None if unsupported."""
    kwargs: dict = {}
    if system_prompt:
        kwargs["system_prompt"] = system_prompt
    if image is not None:
        from ai_api_unified import SupportedDataType

        kwargs["included_types"] = [SupportedDataType.IMAGE]
        kwargs["included_data"] = [image]
        kwargs["included_mime_types"] = [mime_type]

    if engine == "openai":
        from ai_api_unified.completions.ai_openai_completions import (
            AICompletionsPromptParamsOpenAI,
        )

        return AICompletionsPromptParamsOpenAI(**kwargs)
    if engine == "google-gemini":
        from ai_api_unified.completions.ai_google_gemini_capabilities import (
            AICompletionsPromptParamsGoogle,
        )

        return AICompletionsPromptParamsGoogle(**kwargs)
    return None


def _send(prompt: str, *, system_prompt: str | None = None, image_path: Path | None = None) -> None:
    if not state.ensure_capability_ready(CAPABILITY):
        return
    engine = state.current_engine(CAPABILITY)
    with provider_errors():
        image = image_path.read_bytes() if image_path else None
        params = _prompt_params(engine, system_prompt=system_prompt, image=image)
        if (system_prompt or image) and params is None:
            ui.warn(
                f"Engine {engine!r} has no prompt-params support for media/system prompts "
                "in this app; sending the plain prompt instead."
            )
        client = _client()
        ui.info(f"Model: {client.model_name}")
        response = runner.run_call(
            f"Completions via {engine}",
            lambda: (
                client.send_prompt(prompt, other_params=params)
                if params is not None
                else client.send_prompt(prompt)
            ),
        )
        ui.console.print(Panel(response, title="Response", border_style="green"))


def _describe_image(image_path: Path) -> None:
    ui.info(f"Image: {image_path}")
    _send(
        "Describe this image in two sentences, mentioning shapes and colors you see.",
        image_path=image_path,
    )


def _model_info() -> None:
    if not state.ensure_capability_ready(CAPABILITY):
        return
    with provider_errors():
        from ai_api_unified import AIFactory

        client = _client()
        ui.info(f"Model: {client.model_name}")
        ui.info(f"Max context tokens: {client.max_context_tokens:,}")
        ui.info(f"Price per 1k tokens: ${client.price_per_1k_tokens}")
        ui.info("Known models: " + ", ".join(AIFactory.list_completion_models(client)))


def run() -> None:
    while True:
        ui.header(
            "Completions",
            f"engine: {state.current_engine(CAPABILITY) or 'unset'}  "
            f"model: {state.current_model(CAPABILITY) or 'default'}",
        )
        picked = ui.choose(
            "Completions demos",
            [
                ui.MenuOption("Send a sample prompt", "sample"),
                ui.MenuOption("Send a custom prompt", "custom"),
                ui.MenuOption("System-prompt demo", "system"),
                ui.MenuOption("Describe a bundled sample image", "image"),
                ui.MenuOption("Describe an image from a path", "image_path"),
                ui.MenuOption("Model info (context, price, model list)", "info"),
                ui.MenuOption("Switch engine", "engine"),
                ui.MenuOption("Switch model", "model"),
            ],
        )
        if picked is None:
            return
        if picked.value == "sample":
            prompt = ui.choose_value("Pick a sample prompt", list(samples.COMPLETION_PROMPTS))
            if prompt:
                _send(prompt)
        elif picked.value == "custom":
            prompt = ui.ask("Your prompt")
            if prompt:
                _send(prompt)
        elif picked.value == "system":
            options = [
                ui.MenuOption(f"{sys_p[:44]}… / {user_p}", (sys_p, user_p))
                for sys_p, user_p in samples.SYSTEM_PROMPT_DEMOS
            ]
            chosen = ui.choose("Pick a persona demo", options)
            if chosen:
                system_prompt, user_prompt = chosen.value
                _send(user_prompt, system_prompt=system_prompt)
        elif picked.value == "image":
            images = samples.sample_image_paths()
            if not images:
                ui.error("No bundled images found — run: make assets")
                continue
            chosen_path = ui.choose(
                "Pick a sample image", [ui.MenuOption(p.name, p) for p in images]
            )
            if chosen_path:
                _describe_image(chosen_path.value)
        elif picked.value == "image_path":
            raw = ui.ask("Path to a PNG/JPEG image")
            path = Path(raw).expanduser()
            if raw and path.exists():
                _describe_image(path)
            elif raw:
                ui.error(f"No such file: {path}")
        elif picked.value == "info":
            _model_info()
        elif picked.value == "engine":
            state.switch_engine_menu(CAPABILITY)
        elif picked.value == "model":
            state.switch_model_menu(CAPABILITY)
