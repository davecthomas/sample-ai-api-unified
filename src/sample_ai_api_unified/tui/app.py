"""The Textual application: sidebar navigation plus a swappable content pane.

Every capability has a full Textual screen. Non-UI logic (catalog, state,
envfile, onboarding, obs, samples, promptgen) lives in standalone modules.
"""

from __future__ import annotations

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Label, ListItem, ListView

from .. import clipboard, envfile, obs, state
from .screens.base import CapabilityScreen
from .screens.completions import CompletionsScreen
from .screens.embeddings import EmbeddingsScreen
from .screens.images import ImagesScreen
from .screens.middleware import MiddlewareScreen
from .screens.providers import ProvidersScreen
from .screens.structured import StructuredScreen
from .screens.videos import VideosScreen
from .screens.voice import VoiceScreen

# (label, capability/screen key)
NAV: tuple[tuple[str, str], ...] = (
    ("Completions", "completions"),
    ("Structured responses", "structured"),
    ("Embeddings", "embeddings"),
    ("Image generation", "images"),
    ("Video generation", "videos"),
    ("Voice (TTS / STT)", "voice"),
    ("Middleware", "middleware"),
    ("Providers & models", "providers"),
)

SCREENS: dict[str, type[CapabilityScreen]] = {
    "completions": CompletionsScreen,
    "structured": StructuredScreen,
    "embeddings": EmbeddingsScreen,
    "images": ImagesScreen,
    "videos": VideosScreen,
    "voice": VoiceScreen,
    "middleware": MiddlewareScreen,
    "providers": ProvidersScreen,
}


class SampleApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "ai-api-unified sample"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "nav('completions')", "Completions"),
        ("e", "nav('embeddings')", "Embeddings"),
        ("p", "nav('providers')", "Providers"),
        ("o", "toggle_obs", "Obs pane"),
        ("y", "copy_result", "Copy result"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                yield Label("ai-api-unified", id="sidebar-title")
                items = [ListItem(Label(label)) for label, _key in NAV]
                yield ListView(*items, id="nav")
            yield Container(id="content")
        yield Footer()

    def on_mount(self) -> None:
        envfile.ensure_env_file()
        envfile.reload_env()
        obs.install()
        self._log_path = obs.enable_file_logging()
        self.show_screen("completions")

    # ── navigation ───────────────────────────────────────────────────

    @on(ListView.Selected, "#nav")
    def _nav_selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is not None and 0 <= index < len(NAV):
            self.show_screen(NAV[index][1])

    def action_nav(self, key: str) -> None:
        self.show_screen(key)

    def action_toggle_obs(self) -> None:
        """Expand/collapse the current screen's observability pane."""
        from textual.css.query import NoMatches
        from textual.widgets import Collapsible

        try:
            screen = self.query_one("#content", Container).query_one(CapabilityScreen)
            panel = screen.query_one("#obs-panel", Collapsible)
        except NoMatches:
            return
        if panel.collapsed:
            # Expand and scroll into view via the screen's shared reveal path.
            screen.reveal_obs_panel()
        else:
            panel.collapsed = True

    def action_copy_result(self) -> None:
        """Copy the current screen's result text (errors included) to the clipboard."""
        from textual.css.query import NoMatches

        try:
            screen = self.query_one("#content", Container).query_one(CapabilityScreen)
        except NoMatches:
            return
        text = getattr(screen, "_last_result", "")
        if not text:
            self.notify("Nothing to copy yet.", severity="warning")
            return
        if clipboard.copy_to_clipboard(text):
            self.notify("Copied result to the clipboard.")
        else:
            # No OS clipboard tool found (e.g. headless/SSH). Fall back to the
            # terminal's OSC 52 clipboard, which works only where supported.
            self.copy_to_clipboard(text)
            self.notify(
                "Sent to the terminal clipboard (OSC 52); paste may not work " "in every terminal.",
                severity="warning",
            )

    def show_screen(self, key: str) -> None:
        content = self.query_one("#content", Container)
        content.remove_children()
        content.mount(self._build_screen(key))
        # Keep the sidebar highlight in sync however navigation was triggered.
        index = next((i for i, (_, nav_key) in enumerate(NAV) if nav_key == key), None)
        if index is not None:
            nav = self.query_one("#nav", ListView)
            if nav.index != index:
                nav.index = index

    def _build_screen(self, key: str) -> CapabilityScreen:
        return SCREENS[key]()

    # ── readiness ────────────────────────────────────────────────────

    def ensure_capability_ready(self, capability_key: str) -> bool:
        """True when the capability's engine is selected and its provider has
        credentials. Onboarding itself happens on the Providers screen."""
        return state.capability_ready(capability_key)


def main() -> None:
    SampleApp().run()


if __name__ == "__main__":
    main()
