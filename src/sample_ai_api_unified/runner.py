"""Run a provider call with a live observability pane.

The call runs in a worker thread while the main thread renders a Rich Live
panel: a spinner with elapsed time on top, and the most recent observability
events (from obs.py) underneath. When observability middleware is disabled the
pane says so instead of staying blank.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from . import obs, ui

T = TypeVar("T")


def _event_panel() -> Panel:
    lines = obs.tail()
    if lines:
        body: Any = Text("\n".join(lines), style="dim")
    else:
        body = Text(
            "No observability events yet — enable the observability middleware "
            "in the Middleware menu to see live call metadata here.",
            style="dim italic",
        )
    return Panel(body, title="Observability events", border_style="magenta")


def run_call(description: str, call: Callable[[], T]) -> T:
    """Execute ``call`` in a thread, rendering live progress; re-raise its error."""
    result: list[Any] = []
    failure: list[BaseException] = []

    def worker() -> None:
        try:
            result.append(call())
        except BaseException as exc:  # noqa: BLE001 - reported to the caller below
            failure.append(exc)

    events_before = obs.event_count()
    thread = threading.Thread(target=worker, daemon=True)
    started = time.monotonic()
    thread.start()

    spinner = Spinner("dots", text=Text(description, style="bold"))
    with Live(console=ui.console, refresh_per_second=8, transient=True) as live:
        while thread.is_alive():
            elapsed = time.monotonic() - started
            spinner.update(text=Text(f"{description} ({elapsed:.0f}s)", style="bold"))
            live.update(Group(spinner, _event_panel()))
            thread.join(timeout=0.12)

    elapsed = time.monotonic() - started
    new_events = obs.events_since(events_before)
    if new_events:
        ui.console.print(
            Panel(
                Text("\n".join(new_events), style="dim"),
                title=f"Observability events ({len(new_events)})",
                border_style="magenta",
            )
        )
    if failure:
        raise failure[0]
    ui.success(f"{description} finished in {elapsed:.1f}s")
    return result[0]
