"""promptgen unit tests with a stubbed completions client (no network)."""

import random
import re

import pytest

pytest.importorskip("ai_api_unified")

from sample_ai_api_unified import promptgen  # noqa: E402


def _literal_segments(template: str) -> list[str]:
    """Every literal run of a template between ``{placeholders}`` — the parts
    that survive a fill.

    Splitting on the whole ``{...}`` pattern yields the literal text only (not
    the placeholder names), including the trailing instruction, so a filled
    prompt must contain all of them (not just the longest one)."""
    segments = re.split(r"\{[^}]*\}", template)
    return [s.strip() for s in segments if s.strip()]


class _FakeClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.seen: str | None = None

    def send_prompt(self, meta: str) -> str:
        self.seen = meta
        return self._reply


@pytest.fixture()
def stub_client(monkeypatch):
    def install(reply: str) -> _FakeClient:
        client = _FakeClient(reply)
        import ai_api_unified

        monkeypatch.setattr(
            ai_api_unified.AIFactory, "get_ai_completions_client", staticmethod(lambda: client)
        )
        return client

    return install


@pytest.mark.parametrize("kind", promptgen.KINDS)
def test_each_kind_generates_and_trims(kind, stub_client):
    client = stub_client('  "a generated prompt"  ')
    result = promptgen.generate_prompt(kind)
    assert result == "a generated prompt"  # quotes and whitespace stripped
    # A filled meta-prompt was sent: every literal segment of the template —
    # including the trailing "reply with only…" instruction — survives, and the
    # {placeholders} were substituted.
    for segment in _literal_segments(promptgen.META_PROMPTS[kind]):
        assert segment in client.seen
    assert "{" not in client.seen and "}" not in client.seen


@pytest.mark.parametrize("kind", promptgen.KINDS)
def test_meta_prompt_varies_across_calls(kind):
    # The core promise of "Generate prompt": repeated calls steer the completions
    # model somewhere new instead of resending an identical instruction.
    rng = random.Random(0)
    seen = {promptgen.build_meta_prompt(kind, rng) for _ in range(50)}
    assert len(seen) > 1
    assert all("{" not in m and "}" not in m for m in seen)


def test_build_meta_prompt_is_deterministic_under_seed():
    a = promptgen.build_meta_prompt("image", random.Random(42))
    b = promptgen.build_meta_prompt("image", random.Random(42))
    assert a == b


def test_unknown_kind_raises(stub_client):
    stub_client("x")
    with pytest.raises(ValueError, match="Unknown prompt kind"):
        promptgen.generate_prompt("not-a-kind")


def test_build_meta_prompt_unknown_kind_raises():
    with pytest.raises(ValueError, match="Unknown prompt kind"):
        promptgen.build_meta_prompt("not-a-kind")


def test_kinds_cover_every_meta_prompt():
    assert set(promptgen.KINDS) == set(promptgen.META_PROMPTS)


def test_generate_related_parses_and_cleans_lines(stub_client):
    client = stub_client(
        '1. "A dog wags its tail."\n'
        "2) Cats groom themselves often.\n"
        "- Puppies chew on shoes.\n"
        "\n"
        "Wolves hunt in packs.\n"
    )
    result = promptgen.generate_related("dogs like to sniff things", count=5)
    assert result == [
        "A dog wags its tail.",
        "Cats groom themselves often.",
        "Puppies chew on shoes.",
        "Wolves hunt in packs.",
    ]
    assert "dogs like to sniff things" in client.seen  # seed passed to the model


def test_generate_related_caps_at_count(stub_client):
    stub_client("one\ntwo\nthree\nfour\nfive\nsix\nseven\n")
    assert promptgen.generate_related("seed", count=3) == ["one", "two", "three"]
