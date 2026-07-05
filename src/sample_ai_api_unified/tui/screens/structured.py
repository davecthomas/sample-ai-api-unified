"""Structured responses screen: schema-validated output and the token guard."""

from __future__ import annotations

import json

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from ... import state
from ...structured_schemas import contact_extraction_class, trip_plan_class
from .base import CapabilityScreen

CAPABILITY = "completions"


class StructuredScreen(CapabilityScreen):
    title_text = "Structured responses"
    subtitle_text = "Schema-validated output via AIStructuredPrompt.strict_schema_prompt."

    # Optional generated source text for contact extraction; None uses the
    # built-in example.
    _source_text: str | None = None

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        with Horizontal(classes="actions"):
            yield Button("Contact extraction", variant="primary", id="contact")
            yield Button("Trip plan", id="trip")
            yield Button("Generate source text", id="generate")
            yield Button("Token-limit guard", id="limit")

    def on_mount(self) -> None:
        engine = state.current_engine(CAPABILITY) or "unset"
        self.query_one("#engine-line", Static).update(f"engine: {engine}")

    def _ready(self) -> bool:
        if self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            return True
        self.set_result("result", "[yellow]Engine not configured.[/yellow]")
        return False

    def _run(self, response_class) -> None:
        if not self._ready():
            return
        prompt = response_class.get_prompt()

        def call() -> str:
            from ai_api_unified import AIFactory

            client = AIFactory.get_ai_completions_client()
            result = client.strict_schema_prompt(
                prompt=prompt,
                response_model=response_class,
                max_response_tokens=2048,
            )
            payload = json.dumps(result.model_dump(exclude={"prompt"}), indent=2)
            # Show the exact prompt sent alongside the validated response.
            return f"Prompt:\n{prompt}\n\nValidated response:\n{payload}"

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Structured response via {state.current_engine(CAPABILITY)}",
        )

    @on(Button.Pressed, "#contact")
    def _on_contact(self) -> None:
        self._run(contact_extraction_class(self._source_text))

    @on(Button.Pressed, "#trip")
    def _on_trip(self) -> None:
        self._run(trip_plan_class())

    @on(Button.Pressed, "#generate")
    def _on_generate(self) -> None:
        def fill(text: str) -> None:
            self._source_text = text
            self.set_result(
                "result",
                f"Generated source text (contact extraction will use it):\n\n{text}",
            )

        self.generate_prompt("structured_text", fill)

    @on(Button.Pressed, "#limit")
    def _on_limit(self) -> None:
        """Show the library rejecting an undersized token budget."""
        if not self._ready():
            return

        def call() -> str:
            from ai_api_unified import AIFactory, StructuredResponseTokenLimitError

            client = AIFactory.get_ai_completions_client()
            try:
                client.strict_schema_prompt(
                    prompt="anything",
                    response_model=contact_extraction_class(),
                    max_response_tokens=64,
                )
            except StructuredResponseTokenLimitError as exc:
                return f"Library rejected the undersized budget:\n\n{exc}"
            return "Expected a StructuredResponseTokenLimitError but the call succeeded."

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description="Token-limit guard rail",
        )
