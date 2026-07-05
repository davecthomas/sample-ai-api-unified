"""promptgen unit tests with a stubbed completions client (no network)."""

import pytest

pytest.importorskip("ai_api_unified")

from sample_ai_api_unified import promptgen  # noqa: E402


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
    assert client.seen == promptgen.META_PROMPTS[kind]  # the meta-prompt was sent


def test_unknown_kind_raises(stub_client):
    stub_client("x")
    with pytest.raises(ValueError, match="Unknown prompt kind"):
        promptgen.generate_prompt("not-a-kind")


def test_kinds_cover_every_meta_prompt():
    assert set(promptgen.KINDS) == set(promptgen.META_PROMPTS)
