"""Application entry point: startup checks, welcome banner, main menu loop."""

from __future__ import annotations

from pathlib import Path

from . import catalog, envfile, obs, onboarding, state, ui
from .demos import completions, embeddings, images, middleware_demo, structured, videos, voice


def _library_banner() -> None:
    try:
        import ai_api_unified
    except ImportError:
        ui.error("ai_api_unified is not installed in this environment.")
        ui.info("Run 'make setup-local' (local checkout) or 'make setup-pypi' (latest release).")
        raise SystemExit(1) from None

    location = Path(ai_api_unified.__file__).resolve()
    source = "PyPI release" if "site-packages" in str(location) else "local editable checkout"
    ui.header(
        "ai-api-unified sample console",
        f"library {ai_api_unified.__version__} ({source})\n{location.parent}",
    )


def _providers_menu() -> None:
    while True:
        state.show_configuration()
        options = [
            ui.MenuOption(f"Switch {cap.label} engine/model", ("switch", key))
            for key, cap in catalog.CAPABILITIES.items()
        ]
        options.append(ui.MenuOption("Configure provider API keys", ("keys", None)))
        picked = ui.choose("Providers & models", options)
        if picked is None:
            return
        action, key = picked.value
        if action == "switch":
            state.switch_engine_menu(key)
        else:
            provider_options = [
                ui.MenuOption(provider.label, provider) for provider in catalog.PROVIDERS.values()
            ]
            chosen = ui.choose("Configure which provider?", provider_options)
            if chosen:
                provider: catalog.Provider = chosen.value
                if catalog.provider_configured(provider):
                    if ui.confirm(
                        f"{provider.label} is already configured. Re-enter keys?", default=False
                    ):
                        for env_key in provider.env_keys:
                            entered = ui.ask(env_key.name)
                            if entered:
                                envfile.set_env_values({env_key.name: entered})
                        envfile.reload_env()
                        ui.success("Updated and reloaded.")
                else:
                    onboarding.ensure_provider_ready(provider)


def main() -> None:
    envfile.ensure_env_file()
    envfile.reload_env()
    obs.install()
    _library_banner()

    menu_actions = (
        ui.MenuOption("Completions", completions.run),
        ui.MenuOption("Structured responses", structured.run),
        ui.MenuOption("Embeddings", embeddings.run, "text, batch, similarity, multimodal"),
        ui.MenuOption("Image generation", images.run),
        ui.MenuOption("Video generation", videos.run),
        ui.MenuOption("Voice (TTS / STT)", voice.run, "plays through your speakers"),
        ui.MenuOption("Middleware", middleware_demo.run, "observability + PII redaction"),
        ui.MenuOption("Providers & models", _providers_menu, "engines, models, API keys"),
        ui.MenuOption("Show configuration", state.show_configuration),
    )

    while True:
        picked = ui.choose("Main menu", menu_actions, back_label="Quit")
        if picked is None:
            ui.info("Goodbye.")
            return
        picked.value()


if __name__ == "__main__":
    main()
