"""Bundled sample content so every demo works without typing anything."""

from __future__ import annotations

from pathlib import Path

from . import paths

COMPLETION_PROMPTS = (
    "In two sentences, explain why the sky is blue.",
    "Write a haiku about a unified AI API.",
    "List three unusual uses for a paperclip.",
)

SYSTEM_PROMPT_DEMOS = (
    ("You are a pirate. Answer everything in pirate speak.", "How do I make a cup of tea?"),
    ("You are a terse SQL expert. Reply with SQL only.", "Get the ten newest orders."),
)

IMAGE_GEN_PROMPTS = (
    "A watercolor skyline of a coastal city at sunrise, soft pastel palette.",
    "A cozy reading nook in a treehouse, warm lantern light, storybook style.",
    "A retro-futuristic diner on Mars, chrome details, 1950s poster art.",
)

VIDEO_GEN_PROMPTS = (
    "A cinematic tracking shot of a neon train crossing a desert at dusk.",
    "A stop-motion paper city waking up at sunrise.",
    "Gentle ocean waves meeting a rocky coastline at golden hour, wide shot.",
)

EMBED_TEXTS = (
    "The quick brown fox jumps over the lazy dog.",
    "A fast auburn fox leaps above a sleepy hound.",
    "Quarterly revenue grew nine percent on strong cloud demand.",
)

SIMILARITY_PAIRS = (
    (
        "A fast auburn fox leaps above a sleepy hound.",
        "The quick brown fox jumps over the lazy dog.",
    ),
    (
        "The quick brown fox jumps over the lazy dog.",
        "Quarterly revenue grew nine percent on strong cloud demand.",
    ),
)

TTS_SAMPLES = (
    "Hello from ai-api-unified. This sentence was synthesized through the unified voice API.",
    "The five boxing wizards jump quickly, testing every phoneme this voice can produce.",
)

# All PII below is fabricated for redaction demos.
PII_SAMPLES = (
    "Hi, I'm Marcus Delgado. Call me at (415) 555-0143 or email marcus.delgado@example.com.",
    "My SSN is 542-11-9087 and my card ends in 4421, billing zip 60614.",
    "Ship it to Priya Natarajan, 88 Willowbrook Lane, Austin, TX 78704. DOB 03/14/1988.",
)

MULTIMODAL_CAPTION = "A bold red circle beside a blue square on a white background."


def sample_image_paths() -> list[Path]:
    return sorted(paths.ASSETS_DIR.glob("*.png"))
