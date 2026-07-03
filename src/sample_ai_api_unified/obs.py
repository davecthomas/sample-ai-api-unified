"""Capture ai-api-unified observability events for the live log pane.

The library's observability middleware emits metadata-only events through two
standard Python loggers. A buffering handler on those loggers feeds the Rich
live pane in runner.py and the post-call event dump.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from datetime import datetime

OBSERVABILITY_LOGGERS = (
    "ai_api_unified.middleware.observability",
    "ai_api_unified.middleware.metrics",
)

_BUFFER: deque[str] = deque(maxlen=500)
_installed = False


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        _BUFFER.append(f"[{timestamp}] {record.levelname} {record.getMessage()}")


def install() -> None:
    global _installed
    if _installed:
        return
    handler = _BufferHandler()
    for name in OBSERVABILITY_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        # Events render in the app's own panes; don't also spray raw log lines
        # over the menus (SAMPLE_APP_RAW_LOGS=1 restores them for debugging).
        logger.propagate = os.environ.get("SAMPLE_APP_RAW_LOGS", "") == "1"
    for noisy in ("httpx", "google_genai", "presidio-analyzer", "ai_api_unified"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _installed = True


def clear() -> None:
    _BUFFER.clear()


def tail(count: int = 12) -> list[str]:
    return list(_BUFFER)[-count:]


def all_events() -> list[str]:
    return list(_BUFFER)
