"""Voice client helpers shared by the voice screen."""

from __future__ import annotations

import os


def voice_client():
    """Create the configured voice client, working around a library gap.

    ai-api-unified 2.6.0's AIVoiceOpenAI.text_to_voice reads self.user but the
    class never defines that field, so every call raises AttributeError. Set it
    via object.__setattr__ (pydantic blocks normal assignment) until the library
    ships a fix.
    """
    from ai_api_unified import AIVoiceFactory

    client = AIVoiceFactory.create()
    if not hasattr(client, "user"):
        object.__setattr__(client, "user", os.environ.get("OPENAI_USER", "sample-app"))
    return client


def audio_format_for(client):
    if client.default_audio_format is not None:
        return client.default_audio_format
    formats = client.list_output_formats
    return formats[0] if formats else None
