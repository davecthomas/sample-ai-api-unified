"""Video generation screen: blocking generate with a cost/time confirmation."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

import os

from ... import catalog, paths, samples, state
from ..fileutil import open_file
from ..modals import ChoiceModal, ConfirmModal
from .base import CapabilityScreen

CAPABILITY = "videos"

COST_WARNING = (
    "Video generation can take several minutes and bills real provider credits. Continue?"
)


class VideosScreen(CapabilityScreen):
    title_text = "Video generation"
    subtitle_text = "Blocking generate_video; the artifact is saved and opened."

    def compose_body(self) -> ComposeResult:
        yield Static("", classes="field-label", id="engine-line")
        yield Input(placeholder="Video prompt…", id="prompt")
        with Horizontal(classes="actions"):
            yield Button("Generate video", variant="primary", id="generate")
            yield Button("Sample prompt", id="sample")
            yield Button("Generate prompt", id="gen-prompt")

    def on_mount(self) -> None:
        engine = state.current_engine(CAPABILITY) or "unset"
        # Show the model the next call will actually use (a stale/absent model
        # resolves to the GA default) without writing to .env on a mere mount.
        resolved, _ = state.resolve_model(CAPABILITY)
        model = resolved or "provider default"
        self.query_one("#engine-line", Static).update(f"engine: {engine}   model: {model}")

    def _needs_temp_api_key(self, engine: str) -> bool:
        # Google video downloads its result through the google-genai Files API,
        # which is only available in the Developer (api-key) client — not the
        # Vertex (service-account) client. So a service-account user needs a
        # temporary api-key override for the call to complete.
        provider = catalog.provider_for_engine(CAPABILITY, engine)
        return (
            provider is not None
            and provider.key == "google"
            and catalog.google_uses_service_account()
        )

    def _generate(self, prompt: str) -> None:
        if not prompt.strip():
            self.set_result("result", "[yellow]Enter a prompt first.[/yellow]")
            return
        if not self.app.ensure_capability_ready(CAPABILITY):  # type: ignore[attr-defined]
            self.set_result("result", "[yellow]Engine not configured.[/yellow]")
            return
        engine = state.current_engine(CAPABILITY)
        if self._needs_temp_api_key(engine) and not os.environ.get("GOOGLE_GEMINI_API_KEY"):
            self.set_result(
                "result",
                "[yellow]Google video downloads the result via the Files API, "
                "which needs api-key auth (not available under a service account). "
                "Set GOOGLE_GEMINI_API_KEY (or GOOGLE_AUTH_METHOD=api_key) to run "
                "it.[/yellow]",
            )
            return

        def confirmed(ok: bool) -> None:
            if ok:
                self._run(prompt)

        self.app.push_screen(ConfirmModal(COST_WARNING), confirmed)

    def _run(self, prompt: str) -> None:
        engine = state.current_engine(CAPABILITY)
        # Make sure a valid model is persisted before the factory reads the env,
        # so it does not fall back to the library's default (which may 404).
        state.ensure_supported_model(CAPABILITY)
        temp_api_key = self._needs_temp_api_key(engine)

        def call() -> str:
            from ai_api_unified import AIBaseVideoProperties, AIFactory

            # For a service-account user, run the whole generate+download under a
            # temporary api-key override so the Files API download works; restore
            # after. Nothing is persisted to .env.
            overrides = {"GOOGLE_AUTH_METHOD": "api_key"} if temp_api_key else {}
            with state.temp_env(**overrides):
                client = AIFactory.get_ai_video_client()
                properties = AIBaseVideoProperties(
                    output_dir=paths.VIDEOS_OUTPUT_DIR,
                    timeout_seconds=1200,
                    poll_interval_seconds=10,
                )
                result = client.generate_video(prompt, properties)
            lines = [f"Prompt:\n{prompt}\n", f"Job {result.job.job_id} status: {result.job.status}"]
            for artifact in result.artifacts:
                if artifact.file_path:
                    open_file(Path(artifact.file_path))
                    lines.append(f"Artifact: {artifact.file_path}")
                elif artifact.remote_uri:
                    lines.append(f"Artifact (remote): {artifact.remote_uri}")
            if temp_api_key:
                lines.append(
                    "\n(ran under a temporary api_key auth override; "
                    "your GOOGLE_AUTH_METHOD is unchanged)"
                )
            return "\n".join(lines)

        self.run_blocking(
            call,
            on_success=lambda text: self.set_result("result", text),
            description=f"Generating video via {engine} (blocking)",
        )

    @on(Button.Pressed, "#generate")
    def _on_generate(self) -> None:
        self._generate(self.query_one("#prompt", Input).value)

    @on(Button.Pressed, "#gen-prompt")
    def _on_gen_prompt(self) -> None:
        def fill(text: str) -> None:
            self.query_one("#prompt", Input).value = text
            self.set_result(
                "result", f"Generated prompt (press Generate video to run it):\n\n{text}"
            )

        self.generate_prompt("video", fill)

    @on(Button.Pressed, "#sample")
    def _on_sample(self) -> None:
        options = [(text, text) for text in samples.VIDEO_GEN_PROMPTS]

        def chosen(prompt: str | None) -> None:
            if prompt:
                self.query_one("#prompt", Input).value = prompt
                self._generate(prompt)

        self.app.push_screen(ChoiceModal("Pick a prompt", options), chosen)
