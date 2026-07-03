"""Uniform error handling for real provider calls: report, hint, never crash."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from . import ui


@contextmanager
def provider_errors() -> Iterator[None]:
    try:
        yield
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:  # noqa: BLE001 - the whole point is graceful reporting
        ui.error(f"{type(exc).__name__}: {exc}")
        _hint_for(exc)


def _hint_for(exc: Exception) -> None:
    name = type(exc).__name__
    if name == "AiProviderDependencyUnavailableError":
        ui.info("The provider's optional extra is not installed — run: make setup-local")
    elif name == "AiProviderCapabilityUnsupportedError":
        ui.info("The configured model does not support this input type — try another model.")
    elif name == "StructuredResponseTokenLimitError":
        ui.info("Raise max_response_tokens (the library enforces a 2048 minimum).")
    elif name == "ValueError" and "ENGINE" in str(exc):
        ui.info("Pick an engine in the Providers & models menu first.")
