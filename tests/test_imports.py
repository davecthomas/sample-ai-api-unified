"""Smoke-import every app module. Demo modules import the library lazily, so
this only needs the base ai-api-unified package (no provider extras)."""

import importlib

import pytest

pytest.importorskip("ai_api_unified")

MODULES = (
    "sample_ai_api_unified.app",
    "sample_ai_api_unified.audio",
    "sample_ai_api_unified.catalog",
    "sample_ai_api_unified.envfile",
    "sample_ai_api_unified.guard",
    "sample_ai_api_unified.middleware_profile",
    "sample_ai_api_unified.obs",
    "sample_ai_api_unified.onboarding",
    "sample_ai_api_unified.runner",
    "sample_ai_api_unified.samples",
    "sample_ai_api_unified.state",
    "sample_ai_api_unified.ui",
    "sample_ai_api_unified.demos.completions",
    "sample_ai_api_unified.demos.embeddings",
    "sample_ai_api_unified.demos.images",
    "sample_ai_api_unified.demos.middleware_demo",
    "sample_ai_api_unified.demos.structured",
    "sample_ai_api_unified.demos.videos",
    "sample_ai_api_unified.demos.voice",
)


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name):
    importlib.import_module(module_name)
