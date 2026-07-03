"""Read, write, and hot-reload the app's .env file.

The library constructs a fresh pydantic ``EnvSettings`` on every factory call,
reading both ``os.environ`` and ``.env`` in the working directory, with
``os.environ`` taking precedence. Writing a key here therefore does both:
persist to ``.env`` and set ``os.environ`` so the change applies immediately.
"""

from __future__ import annotations

import os
import shutil

from dotenv import dotenv_values, load_dotenv, set_key

from . import paths, ui


def ensure_env_file() -> None:
    """Create .env if missing, preferring the local library checkout's copy."""
    if paths.ENV_PATH.exists():
        return
    library_env = paths.LOCAL_LIBRARY_DIR / ".env"
    if library_env.exists():
        shutil.copy(library_env, paths.ENV_PATH)
        ui.success(f"Copied .env from {library_env}")
    elif paths.ENV_TEMPLATE_PATH.exists():
        shutil.copy(paths.ENV_TEMPLATE_PATH, paths.ENV_PATH)
        ui.warn("Created .env from env_template — no API keys are set yet.")
    else:
        paths.ENV_PATH.touch()
        ui.warn("Created an empty .env — no API keys are set yet.")


def reload_env() -> None:
    """Load .env into os.environ, overriding stale process values."""
    load_dotenv(paths.ENV_PATH, override=True)


def get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, "") or dotenv_values(paths.ENV_PATH).get(name, "") or default


def set_env_values(values: dict[str, str]) -> None:
    """Persist keys to .env and apply them to the current process."""
    paths.ENV_PATH.touch(exist_ok=True)
    for name, value in values.items():
        set_key(paths.ENV_PATH, name, value, quote_mode="never")
        os.environ[name] = value


def unset_env_value(name: str) -> None:
    os.environ.pop(name, None)
    if paths.ENV_PATH.exists():
        lines = paths.ENV_PATH.read_text().splitlines()
        kept = [line for line in lines if not line.strip().startswith(f"{name}=")]
        paths.ENV_PATH.write_text("\n".join(kept) + ("\n" if kept else ""))
