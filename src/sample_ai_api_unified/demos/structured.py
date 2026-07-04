"""Structured-response demos using AIStructuredPrompt + strict_schema_prompt."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from rich.panel import Panel

from .. import runner, state, ui
from ..guard import provider_errors

CAPABILITY = "completions"


def contact_extraction_class():
    from ai_api_unified import AIStructuredPrompt

    class ContactExtraction(AIStructuredPrompt):
        name: str | None = None
        city: str | None = None
        profession: str | None = None

        @staticmethod
        def get_prompt() -> str:
            return (
                "Extract the person's name, city, and profession from this text: "
                "'Dr. Amara Okafor recently moved her cardiology practice to Lisbon.'"
            )

        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            schema = deepcopy(super().model_json_schema())
            schema["properties"] = {
                "name": {"type": "string"},
                "city": {"type": "string"},
                "profession": {"type": "string"},
            }
            schema["required"] = ["name", "city", "profession"]
            return schema

    return ContactExtraction


def trip_plan_class():
    from ai_api_unified import AIStructuredPrompt

    class TripPlan(AIStructuredPrompt):
        destination: str | None = None
        days: int | None = None
        activities: list[str] | None = None

        @staticmethod
        def get_prompt() -> str:
            return (
                "Plan a three-day trip to Kyoto for someone who loves food and gardens. "
                "Respond with the destination, number of days, and one activity per day."
            )

        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            schema = deepcopy(super().model_json_schema())
            schema["properties"] = {
                "destination": {"type": "string"},
                "days": {"type": "integer"},
                "activities": {"type": "array", "items": {"type": "string"}},
            }
            schema["required"] = ["destination", "days", "activities"]
            return schema

    return TripPlan


def _run_structured(response_class, *, max_tokens: int = 2048) -> None:
    if not state.ensure_capability_ready(CAPABILITY):
        return
    engine = state.current_engine(CAPABILITY)
    with provider_errors():
        from ai_api_unified import AIFactory

        client = AIFactory.get_ai_completions_client()
        ui.console.print(
            Panel(response_class.get_prompt() or "", title="Prompt", border_style="blue")
        )
        result = runner.run_call(
            f"Structured response via {engine}",
            lambda: client.strict_schema_prompt(
                prompt=response_class.get_prompt(),
                response_model=response_class,
                max_response_tokens=max_tokens,
            ),
        )
        payload = result.model_dump(exclude={"prompt"})
        ui.console.print(
            Panel(
                json.dumps(payload, indent=2),
                title="Validated structured response",
                border_style="green",
            )
        )


def _token_limit_demo() -> None:
    """Show the library rejecting an undersized structured token budget."""
    if not state.ensure_capability_ready(CAPABILITY):
        return
    with provider_errors():
        from ai_api_unified import AIFactory, StructuredResponseTokenLimitError

        client = AIFactory.get_ai_completions_client()
        try:
            client.strict_schema_prompt(
                prompt="anything",
                response_model=contact_extraction_class(),
                max_response_tokens=64,
            )
            ui.warn("Expected a StructuredResponseTokenLimitError but the call succeeded.")
        except StructuredResponseTokenLimitError as exc:
            ui.success("Library rejected the undersized budget before calling the provider:")
            ui.console.print(Panel(str(exc), border_style="yellow"))


def run() -> None:
    while True:
        ui.header("Structured responses", f"engine: {state.current_engine(CAPABILITY) or 'unset'}")
        picked = ui.choose(
            "Structured response demos",
            [
                ui.MenuOption("Contact extraction (flat schema)", "contact"),
                ui.MenuOption("Trip plan (schema with array + integer)", "trip"),
                ui.MenuOption("Token-limit guard rail (expected failure)", "limit"),
                ui.MenuOption("Switch engine", "engine"),
            ],
        )
        if picked is None:
            return
        if picked.value == "contact":
            _run_structured(contact_extraction_class())
        elif picked.value == "trip":
            _run_structured(trip_plan_class())
        elif picked.value == "limit":
            _token_limit_demo()
        elif picked.value == "engine":
            state.switch_engine_menu(CAPABILITY)
