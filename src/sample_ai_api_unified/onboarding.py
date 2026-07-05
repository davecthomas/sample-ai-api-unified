"""Provider credential status for the Providers screen.

Interactive onboarding lives in the TUI's OnboardingModal; this module only
reports which providers are configured.
"""

from __future__ import annotations

from . import catalog


def provider_status_rows() -> list[tuple[str, str, str]]:
    """(label, status, detail) rows for the provider status table."""
    rows: list[tuple[str, str, str]] = []
    for provider in catalog.PROVIDERS.values():
        missing = catalog.missing_keys(provider)
        if missing:
            rows.append(
                (provider.label, "[red]missing keys[/red]", ", ".join(k.name for k in missing))
            )
        else:
            rows.append((provider.label, "[green]configured[/green]", ""))
    return rows
