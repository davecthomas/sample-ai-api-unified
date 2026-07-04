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


class CompletionsScreen(CapabilityScreen):
    title_text = "Completions"
    subtitle_text = "Send prompts to the configured completions engine."

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        yield Input(placeholder="Type a prompt, or use a sample below…", id="prompt")
        with Horizontal(classes="actions"):
            yield Button("Send", variant="primary", id="send")
            yield Button("Sample prompt", id="sample")
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
            return client.send_prompt(prompt)

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
