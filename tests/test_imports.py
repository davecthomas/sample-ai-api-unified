"""Smoke-import every app module. Screens import the library lazily, so this
only needs the base ai-api-unified package (no provider extras)."""

import importlib

import pytest

pytest.importorskip("ai_api_unified")

MODULES = (
    "sample_ai_api_unified.audio",
    "sample_ai_api_unified.catalog",
    "sample_ai_api_unified.envfile",
    "sample_ai_api_unified.middleware_profile",
    "sample_ai_api_unified.obs",
    "sample_ai_api_unified.onboarding",
    "sample_ai_api_unified.paths",
    "sample_ai_api_unified.promptgen",
    "sample_ai_api_unified.samples",
    "sample_ai_api_unified.state",
    "sample_ai_api_unified.structured_schemas",
    "sample_ai_api_unified.voice_util",
    "sample_ai_api_unified.tui.app",
    "sample_ai_api_unified.tui.fileutil",
    "sample_ai_api_unified.tui.screens.base",
    "sample_ai_api_unified.tui.screens.completions",
    "sample_ai_api_unified.tui.screens.embeddings",
    "sample_ai_api_unified.tui.screens.images",
    "sample_ai_api_unified.tui.screens.middleware",
    "sample_ai_api_unified.tui.screens.providers",
    "sample_ai_api_unified.tui.screens.structured",
    "sample_ai_api_unified.tui.screens.videos",
    "sample_ai_api_unified.tui.screens.voice",
    "sample_ai_api_unified.tui.modals",
)


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name):
    importlib.import_module(module_name)
