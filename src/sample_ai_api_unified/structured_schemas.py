"""AIStructuredPrompt schema factories used by the structured-responses screen.

Each factory returns a fresh AIStructuredPrompt subclass whose get_prompt() is
the exact text sent to the provider. contact_extraction_class accepts an
optional source_text so a generated sentence can be extracted instead of the
built-in example.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_CONTACT_TEXT = "Dr. Amara Okafor recently moved her cardiology practice to Lisbon."


def contact_extraction_class(source_text: str | None = None):
    from ai_api_unified import AIStructuredPrompt

    text = source_text or DEFAULT_CONTACT_TEXT

    class ContactExtraction(AIStructuredPrompt):
        name: str | None = None
        city: str | None = None
        profession: str | None = None

        @staticmethod
        def get_prompt() -> str:
            return f"Extract the person's name, city, and profession from this text: '{text}'"

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
