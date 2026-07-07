"""Capture ai-api-unified observability events for the live log pane.

The library's observability middleware emits metadata-only events through two
standard Python loggers. A buffering handler on those loggers feeds the Rich
live pane in runner.py and the post-call event dump. Optionally, a file handler
mirrors the observability events (and the library's own logs) to a datestamped
file under ./logs so failures can be inspected after the fact.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from datetime import datetime
from pathlib import Path

OBSERVABILITY_LOGGERS = (
    "ai_api_unified.middleware.observability",
    "ai_api_unified.middleware.metrics",
    # Financial-ops cost topic (library 2.10.0): ai_api_call_cost events land
    # here when the profile's emit_cost is on.
    "ai_api_unified.observability.cost",
)

# Loggers whose output is also mirrored to the log file (beyond the
# observability loggers above): the library itself and the Google SDK, so an
# error like a failed video download is captured with its context.
_FILE_LOGGERS = OBSERVABILITY_LOGGERS + ("ai_api_unified", "google_genai")

_BUFFER: deque[str] = deque(maxlen=500)
_installed = False
_file_handler: logging.Handler | None = None
_total_emitted = 0  # monotonic; unlike len(_BUFFER), unaffected by deque eviction


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global _total_emitted
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        _BUFFER.append(f"[{timestamp}] {record.levelname} {record.getMessage()}")
        _total_emitted += 1


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


def enable_file_logging(log_dir: Path | None = None) -> Path:
    """Mirror observability events and library logs to a datestamped log file.

    Kept separate from ``install`` so tests can capture events in the buffer
    without creating files. Idempotent: repeated calls reuse the one handler.
    Returns the path of the active log file.
    """
    global _file_handler
    from . import paths

    directory = log_dir if log_dir is not None else paths.LOGS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / f"observability-{datetime.now().strftime('%Y-%m-%d')}.log"

    if _file_handler is not None:
        return log_path

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    for name in _FILE_LOGGERS:
        logger = logging.getLogger(name)
        # Lower the level so the file captures the library's INFO/ERROR context
        # (e.g. a failed video download), not just warnings.
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    _file_handler = handler
    # Record where logs go, in both the live pane (buffer) and the file itself.
    logging.getLogger(OBSERVABILITY_LOGGERS[0]).info("File logging enabled -> %s", log_path)
    return log_path


def clear() -> None:
    _BUFFER.clear()


def tail(count: int = 12) -> list[str]:
    return list(_BUFFER)[-count:]


def all_events() -> list[str]:
    return list(_BUFFER)


def event_count() -> int:
    """Total events ever emitted (not capped by the buffer size)."""
    return _total_emitted


def events_since(count: int) -> list[str]:
    """Events emitted after the point where event_count() returned ``count``."""
    new = _total_emitted - count
    if new <= 0:
        return []
    return list(_BUFFER)[-min(new, len(_BUFFER)) :]
