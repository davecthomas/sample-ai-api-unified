"""Base class for capability screens.

Layout, top to bottom: title, subtitle, the screen's controls (inputs and
action buttons), a response region that fills the remaining height and scrolls,
and a collapsible observability pane. A subclass fills in ``compose_body`` with
its controls only; the base owns the response region and the observability pane.
"""

from __future__ import annotations

from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from rich.text import Text
from textual.css.query import NoMatches
from textual.widgets import Collapsible, Label, Static
from textual.worker import WorkerFailed

from ..widgets import ObservabilityLog


class CapabilityScreen(Vertical):
    """A content panel for one capability. Mounted inside the app's #content."""

    #: Human-readable title shown at the top of the screen.
    title_text: str = ""
    #: Optional one-line subtitle.
    subtitle_text: str = ""
    #: Plain text of the most recent result, kept so the user can copy it
    #: (errors included) with the app's "y" binding.
    _last_result: str = ""

    def compose(self) -> ComposeResult:
        yield Label(self.title_text, classes="screen-title")
        if self.subtitle_text:
            yield Label(self.subtitle_text, classes="screen-subtitle", id="subtitle")
        # Controls sit at natural height directly under the header.
        yield from self.compose_body()
        # The response fills the remaining height and scrolls on its own.
        with VerticalScroll(id="result-scroll"):
            yield Static("", id="result")
        # Observability starts collapsed so the response gets the space; toggle
        # with the "o" key binding or by clicking the header.
        with Collapsible(title="Observability events", collapsed=True, id="obs-panel"):
            yield ObservabilityLog()

    def compose_body(self) -> ComposeResult:
        """Override to supply the screen's inputs and action buttons only.

        The base provides the ``#result`` region below the controls, so
        subclasses must not yield their own result widget.
        """
        yield Static("")

    # ── shared helpers ───────────────────────────────────────────────

    def set_result(self, widget_id: str, text: str) -> None:
        # Guard against a worker completing after the user navigated away and
        # this screen (and its widgets) were removed.
        if not self.is_mounted:
            return
        try:
            self.query_one(f"#{widget_id}", Static).update(text)
        except NoMatches:
            return
        if widget_id == "result":
            # Store the markup-free text so "y" can copy it to the clipboard.
            try:
                self._last_result = Text.from_markup(text).plain
            except Exception:
                self._last_result = text

    def run_blocking(
        self,
        call: Callable[[], Any],
        *,
        on_success: Callable[[Any], None],
        description: str = "Working",
        result_id: str = "result",
    ) -> None:
        """Run a blocking library call in a thread worker, then report back.

        The library stays synchronous; Textual's thread worker keeps the UI
        responsive and delivers success/error back on the app thread.
        """
        self.set_result(result_id, f"[dim]{description}…[/dim]")

        async def runner() -> None:
            # exit_on_error=False: a failed provider call is reported in the UI,
            # not fatal to the app (Textual's default would tear the app down).
            worker_obj = self.app.run_worker(
                call, thread=True, exclusive=False, exit_on_error=False
            )
            try:
                value = await worker_obj.wait()
            except WorkerFailed as failed:
                error = failed.error
                self.set_result(result_id, f"[red]{type(error).__name__}: {error}[/red]")
                return
            if self.is_mounted:
                on_success(value)

        self.run_worker(runner(), exclusive=False, exit_on_error=False)

    def run_streaming(
        self,
        open_stream: Callable[[], Any],
        *,
        prefix: str = "",
        description: str = "Streaming",
        result_id: str = "result",
    ) -> None:
        """Consume a provider text-chunk stream, rendering it live in the result pane.

        ``open_stream`` runs on a worker thread and returns an iterator of text
        chunks (e.g. ``client.send_prompt_streaming(prompt)``). Each chunk is
        appended and the pane is updated from the app thread; a provider or
        configuration error is shown in the pane instead of crashing the app.
        """
        self.set_result(result_id, f"{prefix}[dim]{description}…[/dim]")

        def worker() -> None:
            parts: list[str] = []
            try:
                for chunk in open_stream():
                    parts.append(str(chunk))
                    self.app.call_from_thread(
                        self._render_stream, result_id, prefix, "".join(parts), len(parts), False
                    )
            except Exception as error:  # noqa: BLE001 - report any provider/config error
                self.app.call_from_thread(
                    self.set_result, result_id, f"[red]{type(error).__name__}: {error}[/red]"
                )
                return
            self.app.call_from_thread(
                self._render_stream, result_id, prefix, "".join(parts), len(parts), True
            )

        self.run_worker(worker, thread=True, exclusive=False, exit_on_error=False)

    def _render_stream(
        self, result_id: str, prefix: str, text: str, chunk_count: int, done: bool
    ) -> None:
        if not self.is_mounted:
            return
        if done:
            body = f"{prefix}{text}\n\n[dim]— streamed {chunk_count} chunks[/dim]"
        else:
            body = f"{prefix}{text} [dim]▌[/dim]"  # cursor while streaming
        self.set_result(result_id, body)

    def generate_prompt(self, kind: str, fill: Callable[[str], None]) -> None:
        """Generate a fresh prompt of ``kind`` via the completions API.

        Generation uses the completions engine regardless of this screen's own
        capability, so it gates on completions readiness and passes the result
        to ``fill``.
        """
        if not self.app.ensure_capability_ready("completions"):  # type: ignore[attr-defined]
            self.set_result(
                "result",
                "[yellow]Completions engine not configured (needed to generate prompts).[/yellow]",
            )
            return
        from ... import promptgen

        self.run_blocking(
            lambda: promptgen.generate_prompt(kind),
            on_success=fill,
            description="Generating a prompt via completions",
        )
