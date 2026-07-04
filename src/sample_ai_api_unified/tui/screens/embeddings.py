"""Embeddings capability screen: single embed, batch, and cosine similarity."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ... import samples, state
from ..modals import ChoiceModal
from .base import CapabilityScreen

CAPABILITY = "embeddings"


class EmbeddingsScreen(CapabilityScreen):
    title_text = "Embeddings"
    subtitle_text = "Embed text, run a batch, or compare two texts by cosine similarity."

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        yield Input(placeholder="Text to embed…", id="text")
        with Horizontal(classes="actions"):
            yield Button("Embed", variant="primary", id="embed")
            yield Button("Sample text", id="sample")
            yield Button("Batch", id="batch")
            yield Button("Similarity pair", id="similarity")
        yield Static("", classes="result-panel", id="result")

    def on_mount(self) -> None:
        engine = state.current_engine(CAPABILITY) or "unset"
        model = state.current_model(CAPABILITY) or "provider default"
        self.query_one("#engine-line", Static).update(f"engine: {engine}   model: {model}")

    def _ready(self) -> bool:
        if self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            return True
        self.set_result("result", "[yellow]Engine not configured.[/yellow]")
        return False

    def _embed(self, text: str) -> None:
        if not text.strip():
            self.set_result("result", "[yellow]Enter text first.[/yellow]")
            return
        if not self._ready():
            return

        def call() -> str:
            from ai_api_unified import AIFactory

            client = AIFactory.get_ai_embedding_client()
            result = client.generate_embeddings(text)
            vector = result.get("embedding") or []
            head = ", ".join(f"{value:.4f}" for value in vector[:8])
            return f"dimensions: {result.get('dimensions', len(vector))}\n[{head}, …]"

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Embedding via {state.current_engine(CAPABILITY)}",
        )

    @on(Button.Pressed, "#embed")
    def _on_embed(self) -> None:
        self._embed(self.query_one("#text", Input).value)

    @on(Input.Submitted, "#text")
    def _on_submit(self) -> None:
        self._embed(self.query_one("#text", Input).value)

    @on(Button.Pressed, "#sample")
    def _on_sample(self) -> None:
        options = [(text, text) for text in samples.EMBED_TEXTS]

        def chosen(text: str | None) -> None:
            if text:
                self.query_one("#text", Input).value = text
                self._embed(text)

        self.app.push_screen(ChoiceModal("Pick a sample text", options), chosen)

    @on(Button.Pressed, "#batch")
    def _on_batch(self) -> None:
        if not self._ready():
            return

        def call() -> str:
            from ai_api_unified import AIFactory

            client = AIFactory.get_ai_embedding_client()
            results = client.generate_embeddings_batch(list(samples.EMBED_TEXTS))
            lines = [
                f"{str(item.get('text', ''))[:48]} → {item.get('dimensions', '?')} dims"
                for item in results
            ]
            return "\n".join(lines)

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description="Batch embeddings",
        )

    @on(Button.Pressed, "#similarity")
    def _on_similarity(self) -> None:
        if not self._ready():
            return
        text_a, text_b = samples.SIMILARITY_PAIRS[0]

        def call() -> str:
            from ai_api_unified import AIFactory
            from ai_api_unified.util import similarity_score

            client = AIFactory.get_ai_embedding_client()
            score = similarity_score(
                client.generate_embeddings(text_a), client.generate_embeddings(text_b)
            )
            return f'"{text_a}"\n"{text_b}"\n\ncosine similarity = {score:.4f}'

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description="Embedding two texts for similarity",
        )
