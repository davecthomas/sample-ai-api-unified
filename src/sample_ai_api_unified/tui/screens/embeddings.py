"""Embeddings capability screen: single embed, batch, and cosine similarity."""

from __future__ import annotations

import contextlib
import os

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ... import catalog, samples, state
from ..modals import ChoiceModal
from .base import CapabilityScreen

CAPABILITY = "embeddings"
MULTIMODAL_MODEL = "gemini-embedding-2"


@contextlib.contextmanager
def _google_api_key_auth():
    """Temporarily force Google ``api_key`` auth, then restore the previous mode.

    Multimodal media embeddings only work under api-key auth (the google-genai
    SDK sends only text to the Vertex ``embedContent`` endpoint under a service
    account). Running the demo under a temporary override lets a service-account
    user try it without editing ``.env``, as long as a Gemini API key is set.
    """
    previous = os.environ.get("GOOGLE_AUTH_METHOD")
    os.environ["GOOGLE_AUTH_METHOD"] = "api_key"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("GOOGLE_AUTH_METHOD", None)
        else:
            os.environ["GOOGLE_AUTH_METHOD"] = previous


class EmbeddingsScreen(CapabilityScreen):
    title_text = "Embeddings"
    subtitle_text = "Embed, batch, rank generated sentences by similarity, or compare two texts."

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        yield Input(placeholder="A phrase, e.g. dogs like to sniff things…", id="text")
        with Horizontal(classes="actions"):
            yield Button("Embed", variant="primary", id="embed")
            yield Button("Related & rank", id="related")
            yield Button("Sample text", id="sample")
        with Horizontal(classes="actions"):
            yield Button("Batch", id="batch")
            yield Button("Similarity pair", id="similarity")
            yield Button("Multimodal", id="multimodal")
            yield Button("Capabilities", id="caps")

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

    @on(Button.Pressed, "#related")
    def _on_related(self) -> None:
        seed = self.query_one("#text", Input).value.strip()
        if not seed:
            self.set_result("result", "[yellow]Enter a phrase first.[/yellow]")
            return
        # Generation uses the completions engine; ranking uses the embeddings
        # engine. Both must be configured.
        if not self.app.ensure_capability_ready("completions"):  # type: ignore[attr-defined]
            self.set_result(
                "result",
                "[yellow]Completions engine not configured "
                "(needed to generate related sentences).[/yellow]",
            )
            return
        if not self._ready():
            return

        def call() -> str:
            from ai_api_unified import AIFactory
            from ai_api_unified.util import similarity_score

            from ... import promptgen

            sentences = promptgen.generate_related(seed, count=5)
            if not sentences:
                return "[yellow]The model returned no related sentences.[/yellow]"

            client = AIFactory.get_ai_embedding_client()
            seed_embedding = client.generate_embeddings(seed)
            scored = [
                (similarity_score(seed_embedding, client.generate_embeddings(sentence)), sentence)
                for sentence in sentences
            ]
            scored.sort(key=lambda pair: pair[0], reverse=True)

            lines = [
                f'seed: "{seed}"',
                f"engine: {state.current_engine(CAPABILITY)}   "
                f"model: {state.current_model(CAPABILITY) or 'provider default'}",
                "",
                "Generated sentences ranked by cosine similarity to the seed:",
                "",
            ]
            for score, sentence in scored:
                lines.append(f"{score:.4f}  {sentence}")
            return "\n".join(lines)

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description="Generating related sentences and ranking by similarity",
        )

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

    @on(Button.Pressed, "#caps")
    def _on_caps(self) -> None:
        if not self._ready():
            return

        def call() -> str:
            from ai_api_unified import AIFactory

            caps = AIFactory.get_ai_embedding_client().capabilities
            types = ", ".join(t.value for t in caps.supported_data_types)
            return (
                f"Supported input types: {types}\n"
                f"Default dimensions: {caps.default_dimensions}\n"
                f"Max input tokens: {caps.max_input_tokens}\n"
                f"Max batch size: {caps.max_batch_size}"
            )

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description="Reading model capabilities",
        )

    @on(Button.Pressed, "#multimodal")
    def _on_multimodal(self) -> None:
        # Multimodal image embeddings need google-gemini + gemini-embedding-2 and
        # api-key auth (the google-genai SDK sends only text to the Vertex
        # embedContent endpoint under a service account). Under a service
        # account, run the call with a temporary api_key override if a Gemini API
        # key is available; otherwise say what to set.
        temp_api_key = catalog.google_uses_service_account()
        if temp_api_key and not os.environ.get("GOOGLE_GEMINI_API_KEY"):
            self.set_result(
                "result",
                "[yellow]Multimodal image embeddings need API-key auth: the "
                "google-genai SDK sends only text to Vertex under a service "
                "account. Set GOOGLE_GEMINI_API_KEY (or GOOGLE_AUTH_METHOD=api_key) "
                "to run this demo.[/yellow]",
            )
            return
        if not temp_api_key:
            # Already on api-key auth: confirm the provider is configured before
            # switching, so a failed attempt never silently changes the default.
            provider = catalog.provider_for_engine(CAPABILITY, "google-gemini")
            if provider is not None and not catalog.provider_configured(provider):
                self.set_result(
                    "result",
                    "[yellow]Multimodal needs google-gemini configured "
                    "(set it up on the Providers screen).[/yellow]",
                )
                return
        engine = state.current_engine(CAPABILITY)
        model = state.current_model(CAPABILITY)
        if not (engine == "google-gemini" and model == MULTIMODAL_MODEL):
            state.set_engine(CAPABILITY, "google-gemini", MULTIMODAL_MODEL)
            self.on_mount()  # refresh the engine line
        images = samples.sample_image_paths()
        if not images:
            self.set_result("result", "[yellow]No bundled images found — run: make assets[/yellow]")
            return
        options = [(p.name, p) for p in images]

        def chosen(image_path) -> None:
            if image_path is None:
                return

            def call() -> str:
                from ai_api_unified import (
                    AIEmbeddingsMultimodalParams,
                    AIFactory,
                    SupportedDataType,
                )
                from ai_api_unified.util import similarity_score

                # Force api-key auth for this call when the user is on a service
                # account (media embeddings require it); otherwise leave auth as-is.
                auth = _google_api_key_auth() if temp_api_key else contextlib.nullcontext()
                with auth:
                    client = AIFactory.get_ai_embedding_client()
                    image_bytes = image_path.read_bytes()
                    params = AIEmbeddingsMultimodalParams(
                        text=samples.MULTIMODAL_CAPTION,
                        included_types=[SupportedDataType.IMAGE],
                        included_data=[image_bytes],
                        included_mime_types=["image/png"],
                    )
                    result = client.generate_embeddings_multimodal(params)
                    text_result = client.generate_embeddings(samples.MULTIMODAL_CAPTION)
                score = similarity_score(result, text_result)
                note = (
                    "\n\n(ran under a temporary api_key auth override; your "
                    "GOOGLE_AUTH_METHOD is unchanged)"
                    if temp_api_key
                    else ""
                )
                return (
                    f"Caption: {samples.MULTIMODAL_CAPTION}\n"
                    f"Image: {image_path.name}\n\n"
                    f"dimensions: {result.get('dimensions')}\n"
                    f"cross-modal cosine similarity: {score:.4f}{note}"
                )

            self.run_blocking(
                call,
                on_success=lambda text: self.set_result("result", text),
                description="Multimodal embedding (image + caption)",
            )

        self.app.push_screen(ChoiceModal("Pick an image to embed", options), chosen)
