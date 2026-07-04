"""The Textual application: sidebar navigation plus a swappable content pane.

Non-UI logic (catalog, state, envfile, onboarding, obs, samples) is shared with
the classic Rich app. Core capabilities have full Textual screens; the rest
show a placeholder pointing at ``make run-classic`` until their screens land in
a follow-up PR.
"""

from __future__ import annotations

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Label, ListItem, ListView

from .. import catalog, envfile, obs, state
from .screens.base import CapabilityScreen
from .screens.completions import CompletionsScreen
from .screens.embeddings import EmbeddingsScreen
from .screens.placeholder import PlaceholderScreen
from .screens.providers import ProvidersScreen

# (label, capability/screen key, is_core)
NAV: tuple[tuple[str, str, bool], ...] = (
    ("Completions", "completions", True),
    ("Embeddings", "embeddings", True),
    ("Providers & models", "providers", True),
    ("Structured responses", "structured", False),
    ("Image generation", "images", False),
    ("Video generation", "videos", False),
    ("Voice (TTS / STT)", "voice", False),
    ("Middleware", "middleware", False),
)


class SampleApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "ai-api-unified sample"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "nav('completions')", "Completions"),
        ("e", "nav('embeddings')", "Embeddings"),
        ("p", "nav('providers')", "Providers"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                yield Label("ai-api-unified", id="sidebar-title")
                items = [
                    ListItem(Label(label), classes="-core" if core else "-soon")
                    for label, _key, core in NAV
                ]
                yield ListView(*items, id="nav")
            yield Container(id="content")
        yield Footer()

    def on_mount(self) -> None:
        envfile.ensure_env_file()
        envfile.reload_env()
        obs.install()
        self.show_screen("completions")

    # ── navigation ───────────────────────────────────────────────────

    @on(ListView.Selected, "#nav")
    def _nav_selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is not None and 0 <= index < len(NAV):
            self.show_screen(NAV[index][1])

    def action_nav(self, key: str) -> None:
        self.show_screen(key)

    def show_screen(self, key: str) -> None:
        content = self.query_one("#content", Container)
        content.remove_children()
        content.mount(self._build_screen(key))
        # Keep the sidebar highlight in sync however navigation was triggered.
        index = next((i for i, (_, nav_key, _) in enumerate(NAV) if nav_key == key), None)
        if index is not None:
            nav = self.query_one("#nav", ListView)
            if nav.index != index:
                nav.index = index

    def _build_screen(self, key: str) -> CapabilityScreen:
        if key == "completions":
            return CompletionsScreen()
        if key == "embeddings":
            return EmbeddingsScreen()
        if key == "providers":
            return ProvidersScreen()
        label = next(label for label, nav_key, _ in NAV if nav_key == key)
        return PlaceholderScreen(label)

    # ── readiness ────────────────────────────────────────────────────

    def ensure_capability_ready(self, capability_key: str) -> bool:
        """True when the capability's engine is selected and its provider has
        credentials. Onboarding itself happens on the Providers screen."""
        selector = state.current_engine(capability_key)
        if not selector:
            return False
        provider = catalog.provider_for_engine(capability_key, selector)
        if provider is None:
            return True  # custom selector; let the library validate it
        return catalog.provider_configured(provider)


def main() -> None:
    SampleApp().run()


if __name__ == "__main__":
    main()
