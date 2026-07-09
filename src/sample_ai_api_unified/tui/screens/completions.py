"""Completions capability screen: prompt entry, samples, and model info."""

from __future__ import annotations

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ... import catalog, samples, state
from ..modals import ChoiceModal
from .base import CapabilityScreen

CAPABILITY = "completions"

# Batch completions (library 2.13.0, claude engine). Small demo batch; poll live
# on a worker thread with a bounded wait — real batches finish server-side, so
# on timeout the batch id is reported rather than blocking indefinitely.
BATCH_TIMEOUT_SECONDS = 300.0
BATCH_POLL_SECONDS = 15.0

# The pricing registry keys providers as openai/google/bedrock; the app's AWS
# provider key maps to "bedrock" there.
_REGISTRY_PROVIDER = {"aws": "bedrock"}


def _batch_status_text(job) -> str:
    """One-line live status while a batch is processing."""
    parts = [f"status {job.status.value}"]
    for field, label in (
        ("processing_count", "processing"),
        ("succeeded_count", "succeeded"),
        ("errored_count", "errored"),
    ):
        value = getattr(job, field, None)
        if value:
            parts.append(f"{value} {label}")
    return f"Batch {job.batch_id}\n" + ", ".join(parts) + "\n\n(polling; batches are asynchronous)"


def _batch_results_text(job, results, prompt_by_id: dict[str, str]) -> str:
    """The ended batch: a per-request block keyed by custom_id (results arrive
    out of order, so sort for a stable view)."""
    header = (
        f"Batch {job.batch_id} — {job.status.value}\n"
        f"{job.succeeded_count or 0} succeeded, {job.errored_count or 0} errored "
        f"of {job.request_count or len(results)}\n"
    )
    blocks = [header]
    for item in sorted(results, key=lambda r: r.custom_id):
        prompt = prompt_by_id.get(item.custom_id, "")
        body = item.text if item.text is not None else (item.error_message or "")
        tokens = ""
        if item.provider_completion_tokens is not None:
            tokens = (
                f"  [{item.provider_prompt_tokens or 0} in / "
                f"{item.provider_completion_tokens} out tokens]"
            )
        blocks.append(
            f"[{item.custom_id}] {item.status.value}{tokens}\n"
            f"  prompt: {prompt}\n"
            f"  reply:  {body.strip()}"
        )
    return "\n\n".join(blocks)


def _model_info(model_name: str):
    """The pricing registry's lifecycle/pricing entry for the current model."""
    from ai_api_unified.pricing import get_model_info

    provider = catalog.provider_for_engine(CAPABILITY, state.current_engine(CAPABILITY))
    if provider is None:
        return None
    key = _REGISTRY_PROVIDER.get(provider.key, provider.key)
    return get_model_info(key, model_name)


DESCRIBE_PROMPT = "Describe this image in two sentences, mentioning shapes and colors you see."


def _prompt_params(engine: str, *, system_prompt=None, image=None, mime_type="image/png"):
    """Provider-specific prompt params for system prompts / image input, or None."""
    kwargs: dict = {}
    if system_prompt:
        kwargs["system_prompt"] = system_prompt
    if image is not None:
        from ai_api_unified import SupportedDataType

        kwargs["included_types"] = [SupportedDataType.IMAGE]
        kwargs["included_data"] = [image]
        kwargs["included_mime_types"] = [mime_type]

    if engine == "openai":
        from ai_api_unified.completions.ai_openai_completions import (
            AICompletionsPromptParamsOpenAI,
        )

        return AICompletionsPromptParamsOpenAI(**kwargs)
    if engine == "google-gemini":
        from ai_api_unified.completions.ai_google_gemini_capabilities import (
            AICompletionsPromptParamsGoogle,
        )

        return AICompletionsPromptParamsGoogle(**kwargs)
    if engine == "claude":
        # The native Anthropic engine takes the base params directly (it honors
        # system_prompt and image attachments without a provider subclass).
        from ai_api_unified.ai_base import AICompletionsPromptParamsBase

        return AICompletionsPromptParamsBase(**kwargs)
    return None


class CompletionsScreen(CapabilityScreen):
    title_text = "Completions"
    subtitle_text = "Send for a full reply, or Stream to watch the response arrive live."

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        yield Input(placeholder="Type a prompt, or use a sample below…", id="prompt")
        with Horizontal(classes="actions"):
            yield Button("Send", variant="primary", id="send")
            yield Button("Stream", id="stream")
        with Horizontal(classes="actions"):
            yield Button("Sample prompt", id="sample")
            yield Button("Generate prompt", id="generate")
        with Horizontal(classes="actions"):
            yield Button("System prompt", id="system")
            yield Button("Describe image", id="describe")
            yield Button("Model info", id="info")
            yield Button("Count tokens", id="count")
        with Horizontal(classes="actions"):
            yield Button("Batch", id="batch")

    def on_mount(self) -> None:
        self._refresh_engine_line()

    def _refresh_engine_line(self) -> None:
        engine = state.current_engine(CAPABILITY) or "unset"
        model = state.current_model(CAPABILITY) or "provider default"
        self.query_one("#engine-line", Static).update(f"engine: {engine}   model: {model}")

    def _send(self, prompt: str) -> None:
        if not prompt.strip():
            self.set_result("result", "[yellow]Enter a prompt first.[/yellow]")
            return
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return

        def call() -> str:
            from ai_api_unified import AIFactory

            client = AIFactory.get_ai_completions_client()
            reply = client.send_prompt(prompt)
            # escape() so bracketed prompt/response text renders literally rather
            # than being parsed as Rich markup.
            return f"Prompt:\n{escape(prompt)}\n\nResponse:\n{escape(reply)}"

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Completions via {state.current_engine(CAPABILITY)}",
        )

    @on(Button.Pressed, "#send")
    def _on_send(self) -> None:
        self._send(self.query_one("#prompt", Input).value)

    @on(Input.Submitted, "#prompt")
    def _on_submit(self) -> None:
        self._send(self.query_one("#prompt", Input).value)

    def _stream(self, prompt: str) -> None:
        if not prompt.strip():
            self.set_result("result", "[yellow]Enter a prompt first.[/yellow]")
            return
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return
        # The library refuses to stream while PII redaction is on (redaction
        # cannot be guaranteed across chunk boundaries). Check up front for a
        # clear message instead of a mid-stream error.
        from ... import middleware_profile as mp

        if mp.read_profile().pii.enabled:
            self.set_result(
                "result",
                "[yellow]Streaming is unavailable while PII redaction is enabled "
                "(redaction can't span stream chunks). Disable it on the "
                "Middleware screen to stream.[/yellow]",
            )
            return

        def open_stream():
            from ai_api_unified import AIFactory

            return AIFactory.get_ai_completions_client().send_prompt_streaming(prompt)

        self.run_streaming(
            open_stream,
            prefix=f"Prompt:\n{prompt}\n\nResponse:\n",
            description=f"Streaming via {state.current_engine(CAPABILITY)}",
        )

    @on(Button.Pressed, "#stream")
    def _on_stream(self) -> None:
        self._stream(self.query_one("#prompt", Input).value)

    @on(Button.Pressed, "#generate")
    def _on_generate(self) -> None:
        def fill(text: str) -> None:
            self.query_one("#prompt", Input).value = text
            self.set_result("result", f"Generated prompt (press Send to run it):\n\n{text}")

        self.generate_prompt("completion", fill)

    def _run_with_params(self, user_prompt: str, *, system_prompt=None, image_path=None) -> None:
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return
        engine = state.current_engine(CAPABILITY)

        def call() -> str:
            from ai_api_unified import AIFactory

            image = image_path.read_bytes() if image_path else None
            params = _prompt_params(engine, system_prompt=system_prompt, image=image)
            header = ""
            if system_prompt:
                header += f"System prompt:\n{escape(system_prompt)}\n\n"
            if image_path:
                header += f"Image: {escape(str(image_path))}\n\n"
            if (system_prompt or image) and params is None:
                header += (
                    f"(note: engine {engine!r} has no system-prompt/image support here; "
                    "sent the plain prompt)\n\n"
                )
            header += f"Prompt:\n{escape(user_prompt)}\n\n"
            client = AIFactory.get_ai_completions_client()
            reply = (
                client.send_prompt(user_prompt, other_params=params)
                if params is not None
                else client.send_prompt(user_prompt)
            )
            return f"{header}Response:\n{escape(reply)}"

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Completions via {engine}",
        )

    @on(Button.Pressed, "#system")
    def _on_system(self) -> None:
        options = [
            (f"{sys_p[:40]}… / {user_p}", (sys_p, user_p))
            for sys_p, user_p in samples.SYSTEM_PROMPT_DEMOS
        ]

        def chosen(pair) -> None:
            if pair:
                system_prompt, user_prompt = pair
                self._run_with_params(user_prompt, system_prompt=system_prompt)

        self.app.push_screen(ChoiceModal("Pick a persona demo", options), chosen)

    @on(Button.Pressed, "#describe")
    def _on_describe(self) -> None:
        images = samples.sample_image_paths()
        if not images:
            self.set_result("result", "[yellow]No bundled images found — run: make assets[/yellow]")
            return
        options = [(p.name, p) for p in images]

        def chosen(path) -> None:
            if path:
                self._run_with_params(DESCRIBE_PROMPT, image_path=path)

        self.app.push_screen(ChoiceModal("Pick a sample image", options), chosen)

    @on(Button.Pressed, "#sample")
    def _on_sample(self) -> None:
        options = [(text, text) for text in samples.COMPLETION_PROMPTS]

        def chosen(prompt: str | None) -> None:
            if prompt:
                self.query_one("#prompt", Input).value = prompt
                self._send(prompt)

        self.app.push_screen(ChoiceModal("Pick a sample prompt", options), chosen)

    @on(Button.Pressed, "#info")
    def _on_info(self) -> None:
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return

        def call() -> str:
            from ai_api_unified import AIFactory

            client = AIFactory.get_ai_completions_client()
            models = ", ".join(AIFactory.list_completion_models(client))
            lines = [
                f"Model: {client.model_name}",
                f"Max context tokens: {client.max_context_tokens:,}",
            ]
            # Structured per-modality pricing + lifecycle (library 2.9.0). The
            # blended price_per_1k_tokens is deprecated in favor of these split
            # rates and compute_completion_cost.
            pricing = client.capabilities.pricing
            if pricing is not None and pricing.token_rates is not None:
                rates = pricing.token_rates
                lines.append(
                    f"Pricing (per 1M tokens, {pricing.currency}): "
                    f"input ${rates.input_per_1m}, output ${rates.output_per_1m}"
                    + (
                        f", cached input ${rates.cached_input_per_1m}"
                        if rates.cached_input_per_1m is not None
                        else ""
                    )
                )
                example = client.compute_completion_cost(input_tokens=1_000, output_tokens=500)
                lines.append(
                    f"Example cost (1,000 in + 500 out): ${example:.6f} "
                    "(compute_completion_cost)"
                )
                lines.append(f"Pricing source: {pricing.source}")
            else:
                lines.append("Pricing: not in the library's pricing registry")
            info = _model_info(client.model_name)
            if info is not None:
                lifecycle = info.status.value
                if info.recommended_replacement:
                    lifecycle += f" (replacement: {info.recommended_replacement})"
                lines.append(f"Lifecycle: {lifecycle}")
            lines.append(f"Known models: {models}")
            return escape("\n".join(lines))

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description="Fetching model info",
        )

    @on(Button.Pressed, "#count")
    def _on_count(self) -> None:
        prompt = self.query_one("#prompt", Input).value
        if not prompt.strip():
            self.set_result("result", "[yellow]Enter a prompt to count first.[/yellow]")
            return
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return

        def call() -> str:
            from ai_api_unified import AIFactory

            client = AIFactory.get_ai_completions_client()
            # Provider-side token counting (library 2.8.0) is capability-gated;
            # Bedrock implements it via the CountTokens operation. Check the
            # flag for a clear message instead of the library's exception.
            if not client.capabilities.supports_token_counting:
                # escape(): a custom model name may contain brackets.
                return (
                    f"[yellow]{escape(client.model_name)} does not support provider-side "
                    "token counting. Switch completions to claude or a Bedrock "
                    "engine (e.g. nova) to try count_tokens.[/yellow]"
                )
            count = client.count_tokens(prompt)
            return escape(
                f"Prompt:\n{prompt}\n\nProvider-counted input tokens: {count:,}\n"
                "(counted without running inference)"
            )

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Counting tokens via {state.current_engine(CAPABILITY)}",
        )

    @on(Button.Pressed, "#batch")
    def _on_batch(self) -> None:
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return
        prompts = list(samples.COMPLETION_PROMPTS)
        prompt_by_id = {f"q{index}": prompt for index, prompt in enumerate(prompts, start=1)}
        self.set_result("result", "[dim]Submitting batch…[/dim]")

        def worker() -> None:
            import time

            try:
                from ai_api_unified import AIFactory

                client = AIFactory.get_ai_completions_client()
                # Capability-gated (library 2.13.0); only the claude engine
                # implements batch today. Check before importing the batch types
                # so an older library shows this message rather than an
                # ImportError, and getattr covers the flag being absent entirely.
                if not getattr(client.capabilities, "supports_batch", False):
                    self.app.call_from_thread(
                        self.set_result,
                        "result",
                        f"[yellow]{escape(client.model_name)} does not support batch "
                        "completions (Message Batches). Switch completions to the "
                        "claude engine to try it.[/yellow]",
                    )
                    return
                from ai_api_unified import AIBatchRequestItem

                items = [
                    AIBatchRequestItem(custom_id=cid, prompt=prompt)
                    for cid, prompt in prompt_by_id.items()
                ]
                job = client.submit_batch(items)
                deadline = time.monotonic() + BATCH_TIMEOUT_SECONDS
                while not job.is_terminal:
                    self.app.call_from_thread(
                        self.set_result, "result", escape(_batch_status_text(job))
                    )
                    if time.monotonic() >= deadline:
                        self.app.call_from_thread(
                            self.set_result,
                            "result",
                            escape(
                                f"Batch {job.batch_id} is still processing after "
                                f"{BATCH_TIMEOUT_SECONDS:.0f}s (status {job.status.value}). "
                                "Batches finish server-side (up to ~24h); press Batch "
                                "again later to submit and poll a fresh one."
                            ),
                        )
                        return
                    time.sleep(BATCH_POLL_SECONDS)
                    job = client.get_batch(job)
                results = client.get_batch_results(job)
                self.app.call_from_thread(
                    self.set_result,
                    "result",
                    escape(_batch_results_text(job, results, prompt_by_id)),
                )
            except Exception as error:  # noqa: BLE001 - report any provider/config error
                self.app.call_from_thread(
                    self.set_result,
                    "result",
                    f"[red]{escape(f'{type(error).__name__}: {error}')}[/red]",
                )

        self.run_worker(worker, thread=True, exclusive=False, exit_on_error=False)
