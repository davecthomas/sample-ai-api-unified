"""Base class for capability screens.

Provides the shared layout (title, body, docked observability pane) and helpers
for running blocking provider calls off the UI thread and reporting results. A
subclass fills in ``compose_body`` and its own actions.
"""

from __future__ import annotations

from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
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
        self.query_one(f"#{widget_id}", Static).update(text)

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
            worker_obj = self.app.run_worker(call, thread=True, exclusive=False)
            try:
                value = await worker_obj.wait()
            except WorkerFailed as failed:
                error = failed.error
                self.set_result(result_id, f"[red]{type(error).__name__}: {error}[/red]")
                return
            on_success(value)

        self.run_worker(runner(), exclusive=False)
