"""Every catalog engine selector must resolve in the real library registry."""

import pytest

pytest.importorskip("ai_api_unified")

from ai_api_unified.ai_provider_registry import get_ai_provider_spec  # noqa: E402

from sample_ai_api_unified import catalog  # noqa: E402


@pytest.mark.parametrize("capability_key", list(catalog.CAPABILITIES))
def test_selectors_resolve_in_library_registry(capability_key):
    capability = catalog.CAPABILITIES[capability_key]
    for engine in capability.engines:
        spec = get_ai_provider_spec(capability_key, engine.selector)
        assert spec is not None, f"{engine.selector!r} is not a registered {capability_key} engine"


def test_catalog_covers_all_registry_voice_engines():
    """Voice is small enough to require exhaustive coverage."""
    catalog_selectors = {e.selector for e in catalog.CAPABILITIES["voice"].engines}
    assert catalog_selectors == {"openai", "google", "azure", "elevenlabs"}


# The model-list sync tests import provider modules that live behind optional
# extras. CI installs the base library only, so each import skips when the
# provider SDK is absent; `make setup-local` installs every extra and runs them.


def test_default_models_match_library_defaults():
    """Spot-check that catalog defaults agree with the library's own defaults."""
    google_module = pytest.importorskip("ai_api_unified.videos.ai_google_gemini_videos")
    openai_module = pytest.importorskip("ai_api_unified.videos.ai_openai_videos")

    google_videos = catalog.engine_for("videos", "google-gemini")
    # The library's own DEFAULT_VIDEO_MODEL (veo-3.1-lite-generate-preview) is a
    # preview model Vertex rejects with 404, so the catalog deliberately defaults
    # to a GA model instead. Require only that the catalog default is a model the
    # library actually supports, keeping the catalog within the library's set.
    assert google_videos.default_model in google_module.AIGoogleGeminiVideos.SUPPORTED_VIDEO_MODELS
    openai_videos = catalog.engine_for("videos", "openai")
    assert openai_videos.default_model == openai_module.AIOpenAIVideos.DEFAULT_VIDEO_MODEL
    assert set(openai_videos.models) == set(openai_module.AIOpenAIVideos.SUPPORTED_VIDEO_MODELS)


def test_gemini_completions_models_match_library_specs():
    module = pytest.importorskip("ai_api_unified.completions.ai_google_gemini_completions")
    catalog_models = set(catalog.engine_for("completions", "google-gemini").models)
    assert catalog_models == set(module.GEMINI_MODEL_SPECS)


def test_google_image_models_match_library_list():
    module = pytest.importorskip("ai_api_unified.images.ai_google_gemini_images")
    catalog_models = set(catalog.engine_for("images", "google-gemini").models)
    assert catalog_models == set(module.AIGoogleGeminiImages.SUPPORTED_IMAGE_MODELS)
