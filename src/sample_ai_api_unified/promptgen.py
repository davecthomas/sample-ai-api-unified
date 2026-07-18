"""Generate fresh sample prompts with the completions API.

Each kind maps to a meta-prompt that asks the configured completions model for a
single ready-to-use prompt. The completions engine does the writing regardless
of which capability the prompt is for (e.g. the completions model writes a
video prompt that you then send to the video engine).

A fixed meta-prompt produces a fixed result: completions models sample
deterministically enough that sending the exact same instruction returns the
exact same prompt every time. So each meta-prompt is a template with random
steering ("about {topic}", "in {style} style") drawn fresh on every call. The
steering dimensions are independent, so the joint space is large enough that
back-to-back calls land somewhere new even when the model itself is
deterministic — that is what makes "Generate prompt" actually generate.
"""

from __future__ import annotations

import random

# Steering pools. Combined across independent dimensions per kind, these give
# thousands of distinct meta-prompts, so repeats are rare in practice.
_TOPICS: tuple[str, ...] = (
    "deep-sea exploration",
    "medieval cartography",
    "urban beekeeping",
    "quantum computing",
    "volcanology",
    "jazz improvisation",
    "Arctic wildlife",
    "ancient trade routes",
    "competitive chess",
    "mycology",
    "space telescopes",
    "coral reefs",
    "typography",
    "desert ecology",
    "railway engineering",
    "folklore and myth",
    "coffee cultivation",
    "glassblowing",
    "tidal energy",
    "paleontology",
    "the history of clocks",
    "migratory birds",
    "street food",
    "lighthouse keeping",
    "origami",
    "cave systems",
    "vintage aircraft",
    "bioluminescence",
    "mountain weather",
    "the physics of bubbles",
)

_COMPLETION_ANGLES: tuple[str, ...] = (
    "question",
    "thought experiment",
    "what-if scenario",
    "comparison to reason through",
    "how-would-you challenge",
    "surprising fact to explain",
    "short creative brief",
    "puzzle",
)

_MOODS: tuple[str, ...] = (
    "calm",
    "wistful",
    "playful",
    "awestruck",
    "suspenseful",
    "warm",
    "wry",
    "hopeful",
)

_VIDEO_SUBJECTS: tuple[str, ...] = (
    "a lone traveller",
    "a soaring bird",
    "a vintage train",
    "a drifting jellyfish",
    "a market at dawn",
    "a sailboat",
    "a running fox",
    "a spinning carousel",
)

_VIDEO_SETTINGS: tuple[str, ...] = (
    "a neon-lit city street in the rain",
    "a windswept coastal cliff",
    "a misty pine forest at dawn",
    "a sunlit desert canyon",
    "a snow-covered mountain pass",
    "a bustling night bazaar",
    "an abandoned greenhouse",
    "a quiet harbour at dusk",
)

_CAMERA_MOVES: tuple[str, ...] = (
    "a slow dolly push-in",
    "a sweeping crane shot",
    "a handheld tracking follow",
    "a smooth orbit around the subject",
    "a low-angle tilt up",
    "a drifting aerial pullback",
    "a whip pan into the action",
)

_IMAGE_SUBJECTS: tuple[str, ...] = (
    "a fox curled in autumn leaves",
    "a floating city among clouds",
    "an old clockmaker's workshop",
    "a tide pool teeming with life",
    "a solitary tree on a hill",
    "a robot tending a garden",
    "a paper boat on a puddle",
    "a whale breaching at sunset",
)

_IMAGE_STYLES: tuple[str, ...] = (
    "watercolour",
    "cinematic photorealism",
    "flat vector illustration",
    "oil-painting impasto",
    "isometric 3D render",
    "ink-and-wash",
    "retro travel-poster",
    "low-poly",
)

_IMAGE_LIGHTING: tuple[str, ...] = (
    "golden-hour backlight",
    "soft overcast light",
    "dramatic chiaroscuro",
    "cool moonlight",
    "warm candlelight",
    "high-key studio light",
    "neon glow",
    "dappled forest light",
)

_PROFESSIONS: tuple[str, ...] = (
    "marine biologist",
    "jazz pianist",
    "cartographer",
    "pastry chef",
    "structural engineer",
    "archivist",
    "beekeeper",
    "astronomer",
    "glassblower",
    "wildlife ranger",
    "typographer",
    "seismologist",
)

_CITIES: tuple[str, ...] = (
    "Lisbon",
    "Reykjavik",
    "Kyoto",
    "Montevideo",
    "Marrakech",
    "Wellington",
    "Ljubljana",
    "Valparaíso",
    "Bergen",
    "Chiang Mai",
    "Tbilisi",
    "Halifax",
)

# Templates carry a stable skeleton plus {placeholders} filled from the pools
# above. Keys are the public prompt kinds.
META_PROMPTS: dict[str, str] = {
    "completion": (
        "Write one short, interesting {angle} about {topic} to send to an AI "
        "assistant. Make it specific and original. Reply with only the prompt "
        "itself — no quotes, no preamble."
    ),
    "tts": (
        "Write one vivid {mood} sentence of 12 to 20 words about {topic} that "
        "is pleasant to hear spoken aloud. Reply with only the sentence."
    ),
    "video": (
        "Write one short cinematic text-to-video prompt: a single scene of "
        "{subject} in {setting}, filmed with {camera}. Reply with only the "
        "prompt."
    ),
    "image": (
        "Write one short, vivid text-to-image prompt: {subject}, in {style} "
        "style, lit with {lighting}. Reply with only the prompt."
    ),
    "structured_text": (
        "Write one or two sentences describing a fictional {profession} who "
        "lives in {city}. Include their full name, their city, and their "
        "profession. Invent a fresh, uncommon full name. Reply with only the "
        "sentences."
    ),
}

KINDS = tuple(META_PROMPTS)


def _steering(kind: str, rng: random.Random) -> dict[str, str]:
    """Random fills for ``kind``'s template, one independent pick per slot."""
    if kind == "completion":
        return {"angle": rng.choice(_COMPLETION_ANGLES), "topic": rng.choice(_TOPICS)}
    if kind == "tts":
        return {"mood": rng.choice(_MOODS), "topic": rng.choice(_TOPICS)}
    if kind == "video":
        return {
            "subject": rng.choice(_VIDEO_SUBJECTS),
            "setting": rng.choice(_VIDEO_SETTINGS),
            "camera": rng.choice(_CAMERA_MOVES),
        }
    if kind == "image":
        return {
            "subject": rng.choice(_IMAGE_SUBJECTS),
            "style": rng.choice(_IMAGE_STYLES),
            "lighting": rng.choice(_IMAGE_LIGHTING),
        }
    if kind == "structured_text":
        return {"profession": rng.choice(_PROFESSIONS), "city": rng.choice(_CITIES)}
    # build_meta_prompt validates kind against META_PROMPTS before calling this,
    # and every key has a branch above. Reaching here means a kind was added to
    # META_PROMPTS without steering — a wiring bug, not bad input.
    raise AssertionError(f"No steering defined for prompt kind: {kind!r}")


def build_meta_prompt(kind: str, rng: random.Random | None = None) -> str:
    """Return ``kind``'s meta-prompt with fresh random steering filled in.

    Separated from :func:`generate_prompt` so the randomness is testable without
    a completions client. Pass ``rng`` to make the draw deterministic.
    """
    if kind not in META_PROMPTS:
        raise ValueError(f"Unknown prompt kind: {kind!r}")
    rng = rng or random
    return META_PROMPTS[kind].format(**_steering(kind, rng))


def generate_prompt(kind: str) -> str:
    """Return a freshly generated prompt of the given kind (blocking call)."""
    from ai_api_unified import AIFactory

    meta = build_meta_prompt(kind)
    client = AIFactory.get_ai_completions_client()
    text = client.send_prompt(meta)
    return text.strip().strip('"').strip()


def _clean_line(line: str) -> str:
    """Strip list numbering, bullets, and surrounding quotes from one line."""
    line = line.strip()
    # Drop a leading "1." / "1)" / "-" / "*" / "•" marker if present.
    for marker in ("- ", "* ", "• "):
        if line.startswith(marker):
            line = line[len(marker) :]
            break
    else:
        head, sep, rest = line.partition(" ")
        if sep and head[:-1].isdigit() and head[-1] in ".)":
            line = rest
    return line.strip().strip('"').strip()


def generate_related(seed: str, count: int = 5) -> list[str]:
    """Return ``count`` short sentences related in topic to ``seed`` (blocking).

    Used by the embeddings screen to build a set of topically-similar sentences
    whose distance from the seed can then be scored by cosine similarity.
    """
    from ai_api_unified import AIFactory

    prompt = (
        f"Write exactly {count} short, natural sentences that are related in "
        f'topic to this sentence: "{seed}". Vary how closely each one relates. '
        "Reply with one sentence per line, no numbering, no quotes, no blank lines."
    )
    client = AIFactory.get_ai_completions_client()
    text = client.send_prompt(prompt)
    lines = [_clean_line(line) for line in text.splitlines()]
    sentences = [line for line in lines if line]
    return sentences[:count]
