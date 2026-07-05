"""Completions capability screen: prompt entry, samples, and model info."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ... import samples, state
from ..modals import ChoiceModal
from .base import CapabilityScreen

CAPABILITY = "completions"

DESCRIBE_PROMPT = "Describe this image in two sentences, mentioning shapes and colors you see."


def _prompt_params(engine: str, *, system_prompt=None, image=None, mime_type="image/png"):
    """Provider-specific prompt params for system prompts / image input, or None."""
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


class CompletionsScreen(CapabilityScreen):
    title_text = "Completions"
    subtitle_text = "Send prompts to the configured completions engine."

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        yield Input(placeholder="Type a prompt, or use a sample below…", id="prompt")
        with Horizontal(classes="actions"):
            yield Button("Send", variant="primary", id="send")
            yield Button("Sample prompt", id="sample")
            yield Button("Generate prompt", id="generate")
        with Horizontal(classes="actions"):
            yield Button("System prompt", id="system")
            yield Button("Describe image", id="describe")
            yield Button("Model info", id="info")
        yield Static("", classes="result-panel", id="result")

    def on_mount(self) -> None:
        self._refresh_engine_line()

    def _refresh_engine_line(self) -> None:
        engine = state.current_engine(CAPABILITY) or "unset"
        model = state.current_model(CAPABILITY) or "provider default"
        self.query_one("#engine-line", Static).update(f"engine: {engine}   model: {model}")

    def _send(self, prompt: str) -> None:
        if not prompt.strip():
            self.set_result("result", "[yellow]Enter a prompt first.[/yellow]")
            return
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return

        def call() -> str:
            from ai_api_unified import AIFactory

            client = AIFactory.get_ai_completions_client()
            reply = client.send_prompt(prompt)
            return f"Prompt:\n{prompt}\n\nResponse:\n{reply}"

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Completions via {state.current_engine(CAPABILITY)}",
        )

    @on(Button.Pressed, "#send")
    def _on_send(self) -> None:
        self._send(self.query_one("#prompt", Input).value)

    @on(Input.Submitted, "#prompt")
    def _on_submit(self) -> None:
        self._send(self.query_one("#prompt", Input).value)

    @on(Button.Pressed, "#generate")
    def _on_generate(self) -> None:
        def fill(text: str) -> None:
            self.query_one("#prompt", Input).value = text
            self.set_result("result", f"Generated prompt (press Send to run it):\n\n{text}")

        self.generate_prompt("completion", fill)

    def _run_with_params(self, user_prompt: str, *, system_prompt=None, image_path=None) -> None:
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return
        engine = state.current_engine(CAPABILITY)

        def call() -> str:
            from ai_api_unified import AIFactory

            image = image_path.read_bytes() if image_path else None
            params = _prompt_params(engine, system_prompt=system_prompt, image=image)
            header = ""
            if system_prompt:
                header += f"System prompt:\n{system_prompt}\n\n"
            if image_path:
                header += f"Image: {image_path}\n\n"
            header += f"Prompt:\n{user_prompt}\n\n"
            client = AIFactory.get_ai_completions_client()
            reply = (
                client.send_prompt(user_prompt, other_params=params)
                if params is not None
                else client.send_prompt(user_prompt)
            )
            return f"{header}Response:\n{reply}"

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Completions via {engine}",
        )

    @on(Button.Pressed, "#system")
    def _on_system(self) -> None:
        options = [
            (f"{sys_p[:40]}… / {user_p}", (sys_p, user_p))
            for sys_p, user_p in samples.SYSTEM_PROMPT_DEMOS
        ]

        def chosen(pair) -> None:
            if pair:
                system_prompt, user_prompt = pair
                self._run_with_params(user_prompt, system_prompt=system_prompt)

        self.app.push_screen(ChoiceModal("Pick a persona demo", options), chosen)

    @on(Button.Pressed, "#describe")
    def _on_describe(self) -> None:
        images = samples.sample_image_paths()
        if not images:
            self.set_result("result", "[yellow]No bundled images found — run: make assets[/yellow]")
            return
        options = [(p.name, p) for p in images]

        def chosen(path) -> None:
            if path:
                self._run_with_params(DESCRIBE_PROMPT, image_path=path)

        self.app.push_screen(ChoiceModal("Pick a sample image", options), chosen)

    @on(Button.Pressed, "#sample")
    def _on_sample(self) -> None:
        options = [(text, text) for text in samples.COMPLETION_PROMPTS]

        def chosen(prompt: str | None) -> None:
            if prompt:
                self.query_one("#prompt", Input).value = prompt
                self._send(prompt)

        self.app.push_screen(ChoiceModal("Pick a sample prompt", options), chosen)

    @on(Button.Pressed, "#info")
    def _on_info(self) -> None:
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return

        def call() -> str:
            from ai_api_unified import AIFactory

            client = AIFactory.get_ai_completions_client()
            models = ", ".join(AIFactory.list_completion_models(client))
            return (
                f"Model: {client.model_name}\n"
                f"Max context tokens: {client.max_context_tokens:,}\n"
                f"Price per 1k tokens: ${client.price_per_1k_tokens}\n"
                f"Known models: {models}"
            )

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description="Fetching model info",
        )
