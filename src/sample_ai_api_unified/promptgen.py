"""Generate fresh sample prompts with the completions API.

Each kind maps to a meta-prompt that asks the configured completions model for a
single ready-to-use prompt. The completions engine does the writing regardless
of which capability the prompt is for (e.g. the completions model writes a
video prompt that you then send to the video engine).
"""

from __future__ import annotations

META_PROMPTS: dict[str, str] = {
    "completion": (
        "Write one short, interesting question or instruction to send to an AI "
        "assistant. Reply with only the prompt itself — no quotes, no preamble."
    ),
    "tts": (
        "Write one vivid sentence of 12 to 20 words that is pleasant to hear "
        "spoken aloud. Reply with only the sentence."
    ),
    "video": (
        "Write one short cinematic text-to-video prompt describing a single "
        "scene with camera movement. Reply with only the prompt."
    ),
    "image": (
        "Write one short, vivid text-to-image prompt naming a subject, style, "
        "and lighting. Reply with only the prompt."
    ),
    "structured_text": (
        "Write one or two sentences describing a fictional person, including "
        "their full name, the city they live in, and their profession. Reply "
        "with only the sentences."
    ),
}

KINDS = tuple(META_PROMPTS)


def generate_prompt(kind: str) -> str:
    """Return a freshly generated prompt of the given kind (blocking call)."""
    if kind not in META_PROMPTS:
        raise ValueError(f"Unknown prompt kind: {kind!r}")
    from ai_api_unified import AIFactory

    client = AIFactory.get_ai_completions_client()
    text = client.send_prompt(META_PROMPTS[kind])
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
