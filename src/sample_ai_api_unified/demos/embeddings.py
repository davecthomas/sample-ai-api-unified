"""Embeddings demos: text, batch, similarity, capabilities, and multimodal."""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from .. import runner, samples, state, ui
from ..guard import provider_errors

CAPABILITY = "embeddings"
MULTIMODAL_MODEL = "gemini-embedding-2"


def _client():
    from ai_api_unified import AIFactory

    return AIFactory.get_ai_embedding_client()


def _show_embedding(result: dict) -> None:
    vector = result.get("embedding") or []
    preview = ", ".join(f"{value:.4f}" for value in vector[:8])
    ui.info(f"Dimensions: {result.get('dimensions', len(vector))}")
    if result.get("model"):
        ui.info(f"Model: {result['model']}")
    ui.console.print(Panel(f"[{preview}, …]", title="Vector head", border_style="green"))


def _embed(text: str) -> None:
    if not state.ensure_capability_ready(CAPABILITY):
        return
    with provider_errors():
        client = _client()
        result = runner.run_call(
            f"Embedding via {state.current_engine(CAPABILITY)}",
            lambda: client.generate_embeddings(text),
        )
        _show_embedding(result)


def _batch() -> None:
    if not state.ensure_capability_ready(CAPABILITY):
        return
    with provider_errors():
        client = _client()
        results = runner.run_call(
            f"Batch of {len(samples.EMBED_TEXTS)} embeddings",
            lambda: client.generate_embeddings_batch(list(samples.EMBED_TEXTS)),
        )
        table = Table(title="Batch results", border_style="green")
        table.add_column("Text")
        table.add_column("Dimensions", justify="right")
        for item in results:
            table.add_row(str(item.get("text", ""))[:60], str(item.get("dimensions", "?")))
        ui.console.print(table)


def _similarity(text_a: str, text_b: str) -> None:
    if not state.ensure_capability_ready(CAPABILITY):
        return
    with provider_errors():
        from ai_api_unified.util import similarity_score

        client = _client()
        score = runner.run_call(
            "Embedding two texts for similarity",
            lambda: similarity_score(
                client.generate_embeddings(text_a), client.generate_embeddings(text_b)
            ),
        )
        ui.console.print(
            Panel(
                f'"{text_a}"\n"{text_b}"\n\ncosine similarity = [bold]{score:.4f}[/bold]',
                border_style="green",
            )
        )


def _capabilities() -> None:
    if not state.ensure_capability_ready(CAPABILITY):
        return
    with provider_errors():
        client = _client()
        caps = client.capabilities
        table = Table(title="Embedding model capabilities", border_style="cyan")
        table.add_column("Property", style="bold")
        table.add_column("Value")
        table.add_row(
            "Supported input types", ", ".join(t.value for t in caps.supported_data_types)
        )
        table.add_row("Default dimensions", str(caps.default_dimensions))
        table.add_row("Max input tokens", str(caps.max_input_tokens))
        table.add_row("Max batch size", str(caps.max_batch_size))
        ui.console.print(table)


def _ensure_multimodal_model() -> bool:
    engine = state.current_engine(CAPABILITY)
    model = state.current_model(CAPABILITY)
    if engine == "google-gemini" and model == MULTIMODAL_MODEL:
        return True
    ui.warn(
        f"Multimodal embeddings need google-gemini + {MULTIMODAL_MODEL} "
        f"(current: {engine or 'unset'} / {model or 'default'})."
    )
    if not ui.confirm(f"Switch embeddings to {MULTIMODAL_MODEL} now?", default=True):
        return False
    state.set_engine(CAPABILITY, "google-gemini", MULTIMODAL_MODEL)
    return state.ensure_capability_ready(CAPABILITY)


def _multimodal() -> None:
    if not _ensure_multimodal_model():
        return
    images = samples.sample_image_paths()
    if not images:
        ui.error("No bundled images found — run: make assets")
        return
    chosen = ui.choose("Pick an image to embed", [ui.MenuOption(p.name, p) for p in images])
    if chosen is None:
        return
    image_path = chosen.value

    with provider_errors():
        from ai_api_unified import AIEmbeddingsMultimodalParams, SupportedDataType

        client = _client()
        image_bytes = image_path.read_bytes()

        def embed_image():
            params = AIEmbeddingsMultimodalParams(
                text=samples.MULTIMODAL_CAPTION,
                included_types=[SupportedDataType.IMAGE],
                included_data=[image_bytes],
                included_mime_types=["image/png"],
            )
            return client.generate_embeddings_multimodal(params)

        result = runner.run_call("Multimodal embedding (image + caption)", embed_image)
        _show_embedding(result)

        if ui.confirm("Compare against a text-only embedding of the caption?", default=True):
            from ai_api_unified.util import similarity_score

            text_result = runner.run_call(
                "Text-only embedding of the caption",
                lambda: client.generate_embeddings(samples.MULTIMODAL_CAPTION),
            )
            score = similarity_score(result, text_result)
            ui.success(f"Cross-modal cosine similarity: {score:.4f}")


def run() -> None:
    while True:
        ui.header(
            "Embeddings",
            f"engine: {state.current_engine(CAPABILITY) or 'unset'}  "
            f"model: {state.current_model(CAPABILITY) or 'default'}",
        )
        picked = ui.choose(
            "Embeddings demos",
            [
                ui.MenuOption("Embed a sample text", "sample"),
                ui.MenuOption("Embed custom text", "custom"),
                ui.MenuOption("Batch embeddings", "batch"),
                ui.MenuOption("Similarity: related pair", "sim_related"),
                ui.MenuOption("Similarity: unrelated pair", "sim_unrelated"),
                ui.MenuOption("Similarity: your own two texts", "sim_custom"),
                ui.MenuOption("Multimodal embedding (image + text)", "multimodal"),
                ui.MenuOption("Show model capabilities", "caps"),
                ui.MenuOption("Switch engine", "engine"),
                ui.MenuOption("Switch model", "model"),
            ],
        )
        if picked is None:
            return
        if picked.value == "sample":
            text = ui.choose_value("Pick a text", list(samples.EMBED_TEXTS))
            if text:
                _embed(text)
        elif picked.value == "custom":
            text = ui.ask("Text to embed")
            if text:
                _embed(text)
        elif picked.value == "batch":
            _batch()
        elif picked.value == "sim_related":
            _similarity(*samples.SIMILARITY_PAIRS[0])
        elif picked.value == "sim_unrelated":
            _similarity(*samples.SIMILARITY_PAIRS[1])
        elif picked.value == "sim_custom":
            text_a = ui.ask("First text")
            text_b = ui.ask("Second text")
            if text_a and text_b:
                _similarity(text_a, text_b)
        elif picked.value == "multimodal":
            _multimodal()
        elif picked.value == "caps":
            _capabilities()
        elif picked.value == "engine":
            state.switch_engine_menu(CAPABILITY)
        elif picked.value == "model":
            state.switch_model_menu(CAPABILITY)
