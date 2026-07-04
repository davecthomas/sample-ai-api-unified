"""Filesystem locations used across the app.

The library (via pydantic-settings) reads ``.env`` from the process working
directory, so the app anchors its own ``.env`` there too and expects to be
launched from the repository root (the Makefile does this).
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]

ENV_PATH = Path.cwd() / ".env"
ENV_TEMPLATE_PATH = PROJECT_ROOT / "env_template"
ASSETS_DIR = PROJECT_ROOT / "assets"
CONFIG_DIR = Path.cwd() / "config"
MIDDLEWARE_YAML_PATH = CONFIG_DIR / "middleware.yaml"
IMAGES_OUTPUT_DIR = Path.cwd() / "generated_images"
VIDEOS_OUTPUT_DIR = Path.cwd() / "generated_videos"
FRAMES_OUTPUT_DIR = Path.cwd() / "generated_frames"

# Default location of the local library checkout, used to seed .env.
LOCAL_LIBRARY_DIR = PROJECT_ROOT.parent / "ai_api_unified"
