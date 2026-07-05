"""Base class for capability screens.

Provides the shared layout (title, body, docked observability pane) and helpers
for running blocking provider calls off the UI thread and reporting results. A
subclass fills in ``compose_body`` and its own actions.
"""

from __future__ import annotations

from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Label, Static
from textual.worker import WorkerFailed

from ..widgets import ObservabilityLog


class CapabilityScreen(Vertical):
    """A content panel for one capability. Mounted inside the app's #content."""

    #: Human-readable title shown at the top of the screen.
    title_text: str = ""
    #: Optional one-line subtitle.
    subtitle_text: str = ""

    def compose(self) -> ComposeResult:
        yield Label(self.title_text, classes="screen-title")
        if self.subtitle_text:
            yield Label(self.subtitle_text, classes="screen-subtitle", id="subtitle")
        with VerticalScroll(id="body"):
            yield from self.compose_body()
        yield Label("Observability events", id="obs-title")
        yield ObservabilityLog()

    def compose_body(self) -> ComposeResult:
        """Override to supply the screen's inputs, buttons, and result panels."""
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
            pass

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
