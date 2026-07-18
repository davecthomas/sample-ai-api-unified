"""Structured responses screen: schema-validated output and the token guard."""

from __future__ import annotations

import json

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from ... import state
from ...structured_schemas import contact_extraction_class, trip_plan_class
from .base import CapabilityScreen

CAPABILITY = "completions"


def _finish(finish_reason) -> str:
    return str(getattr(finish_reason, "value", finish_reason))


class StructuredScreen(CapabilityScreen):
    title_text = "Structured responses"
    subtitle_text = (
        "Prompt-engineered strict_schema_prompt, and native send_structured_output (2.15)."
    )

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
        with Horizontal(classes="actions"):
            yield Button("Structured output (native)", id="structured-output")

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

    @on(Button.Pressed, "#structured-output")
    def _on_structured_output(self) -> None:
        """Native single-shot extraction: prose in, a parsed dict out, with a
        normalized finish_reason and token usage — distinct from the older,
        prompt-engineered strict_schema_prompt above."""
        if not self._ready():
            return

        def call() -> dict:
            from ai_api_unified import AIFactory
            from ai_api_unified.middleware import (
                reset_observability_context,
                set_observability_context,
            )

            client = AIFactory.get_ai_completions_client()
            if not client.capabilities.supports_structured_output:
                return {"unsupported": client.model_name}
            model = contact_extraction_class(self._source_text)
            # Observability tags (library 2.14) ride along on the events this
            # call emits, visible in the observability pane; reset afterwards so
            # the context does not leak onto the next call on this thread.
            token = set_observability_context(
                caller_id="sample-app",
                session_id="tui",
                workflow_id="structured-output",
                tags={"screen": "structured", "demo": "send_structured_output"},
            )
            try:
                result = client.send_structured_output(
                    prompt=model.get_prompt(),
                    response_model=model,
                    max_response_tokens=2048,
                )
            finally:
                reset_observability_context(token)
            return {"result": result, "prompt": model.get_prompt()}

        def show(payload: dict) -> None:
            if "unsupported" in payload:
                self.set_result(
                    "result",
                    f"[yellow]{escape(payload['unsupported'])} does not support native "
                    "structured output (supports_structured_output is False). Try claude, "
                    "openai, openai-responses, google-gemini, or a Claude 4.5+ model on "
                    "Bedrock.[/yellow]",
                )
                return
            result = payload["result"]
            usage = result.usage
            data = (
                json.dumps(result.data, indent=2)
                if result.data is not None
                else "(none — data is None on length/refusal; see finish_reason)"
            )
            body = (
                f"Prompt:\n{payload['prompt']}\n\n"
                f"send_structured_output → finish_reason={_finish(result.finish_reason)}\n"
                f"tokens: {usage.input_tokens or 0} in / {usage.output_tokens or 0} out\n\n"
                f"Parsed data:\n{data}"
            )
            self.set_result("result", escape(body))

        self.run_blocking(
            call,
            on_success=show,
            description=f"send_structured_output via {state.current_engine(CAPABILITY)}",
        )

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
