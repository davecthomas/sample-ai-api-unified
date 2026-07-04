"""In-app API-key onboarding.

None of the supported providers offer an SDK/API that can mint an API key
programmatically, so onboarding shows the provider's key-management URL
(offering to open it in the browser), then collects each value with a text
prompt and saves it to .env, applying it to the running process immediately.
"""

from __future__ import annotations

import webbrowser

from . import catalog, envfile, ui


def ensure_provider_ready(provider: catalog.Provider) -> bool:
    """Return True once the provider's required env keys are present."""
    missing = catalog.missing_keys(provider)
    if not missing:
        return True

    ui.header(
        f"{provider.label} is not configured",
        f"Missing: {', '.join(key.name for key in missing)}",
    )
    ui.info(f"Get your credentials here: [bold]{provider.key_url}[/bold]")
    if provider.note:
        ui.warn(provider.note)
    if ui.confirm("Open that page in your browser?", default=False):
        webbrowser.open(provider.key_url)

    if not ui.confirm("Enter the credentials now?", default=True):
        ui.warn(f"Skipped — {provider.label} features stay unavailable until configured.")
        return False

    values: dict[str, str] = {}
    for key in provider.env_keys:
        label = key.name + (" (optional, Enter to skip)" if key.optional else "")
        entered = ui.ask(label, default=key.default if key.optional else "")
        if entered:
            values[key.name] = entered
        elif not key.optional:
            ui.warn(f"{key.name} left blank — aborting {provider.label} setup.")
            return False

    envfile.set_env_values(values)
    envfile.reload_env()
    ui.success(f"Saved to .env and reloaded — {provider.label} is ready.")
    return True


def ensure_engine_ready(capability_key: str, selector: str) -> bool:
    provider = catalog.provider_for_engine(capability_key, selector)
    if provider is None:
        return True  # custom engine selector; let the library validate it
    return ensure_provider_ready(provider)


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
