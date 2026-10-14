"""Model fallback chain (library 2.32): settings and route reporting.

The factory reads ``COMPLETIONS_FALLBACKS`` (ordered ``engine:model`` pairs) on
every call. When it is set, ``get_ai_completions_client()`` returns an
``AiFallbackCompletions`` that retries a failed request on the next candidate,
so every completion-backed screen gets failover with no code change. This
module owns the app's chain settings and the "served by" note shown when a
fallback answered instead of the primary.
"""

from __future__ import annotations

from rich.markup import escape

from . import envfile

FALLBACKS_ENV = "COMPLETIONS_FALLBACKS"
FALLBACK_ON_ENV = "COMPLETIONS_FALLBACK_ON"

# The app's fallback is Gemini. The library's Gemini default completions model.
GEMINI_FALLBACK_ENGINE = "google-gemini"
GEMINI_FALLBACK_MODEL = "gemini-3.7-flash"
GEMINI_FALLBACK = f"{GEMINI_FALLBACK_ENGINE}:{GEMINI_FALLBACK_MODEL}"

# The library default: failures another model could serve. model_unavailable
# (404, unknown or retired model id) is off by default because it usually means
# a typo that a working fallback would hide.
DEFAULT_FALLBACK_ON = "unavailable,rate_limited,quota_exhausted"
FALLBACK_ON_WITH_MODEL = f"{DEFAULT_FALLBACK_ON},model_unavailable"


def current_chain() -> str:
    """The configured chain as written in .env, or "" when off."""
    return envfile.get_env(FALLBACKS_ENV, "").strip()


def current_fallback_on() -> str:
    return envfile.get_env(FALLBACK_ON_ENV, "").strip() or DEFAULT_FALLBACK_ON


def set_chain(chain: str, fallback_on: str = DEFAULT_FALLBACK_ON) -> None:
    envfile.set_env_values({FALLBACKS_ENV: chain, FALLBACK_ON_ENV: fallback_on})


def clear_chain() -> None:
    envfile.unset_env_value(FALLBACKS_ENV)
    envfile.unset_env_value(FALLBACK_ON_ENV)


def route_note(client) -> str:
    """Rich markup naming the fallback that served the last call, else "".

    A plain engine client (no chain) and a call the primary served both return
    "", so screens can append this unconditionally.
    """
    candidates = getattr(client, "candidates", None)
    route = getattr(client, "last_route", None)
    if not candidates or route is None or route == candidates[0]:
        return ""
    return (
        f"\n\n[yellow]Served by fallback {escape(route.label)} "
        f"(primary {escape(candidates[0].label)} failed)[/yellow]"
    )
