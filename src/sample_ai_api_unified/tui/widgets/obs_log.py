"""A docked pane that streams ai-api-unified observability events live.

The library's observability middleware emits metadata-only events through two
standard loggers; ``obs.install()`` buffers them. This widget polls the buffer
on an interval and appends new lines, so enabling the observability middleware
makes provider-call metadata appear here in real time.
"""

from __future__ import annotations

from textual.widgets import RichLog

from ... import obs


class ObservabilityLog(RichLog):
    """RichLog subclass that tails the observability event buffer."""

    def __init__(self) -> None:
        super().__init__(id="obs-log", wrap=True, markup=False, highlight=False)
        self._seen = 0

    def on_mount(self) -> None:
        obs.install()
        self._seen = obs.event_count()
        self.set_interval(0.4, self._drain)

    def _drain(self) -> None:
        new = obs.events_since(self._seen)
        if new:
            for line in new:
                self.write(line)
            # Advance by exactly what was consumed; events emitted between the
            # read above and here are picked up next tick rather than skipped.
            self._seen += len(new)
