"""Sample content sanity: assets exist and PII samples cover the entities."""

from sample_ai_api_unified import samples


def test_bundled_images_exist():
    image_paths = samples.sample_image_paths()
    assert len(image_paths) >= 3
    for path in image_paths:
        assert path.suffix == ".png"
        assert path.stat().st_size > 0


def test_pii_samples_cover_key_entities():
    joined = " ".join(samples.PII_SAMPLES)
    assert "@example.com" in joined  # email
    assert "555" in joined  # phone (reserved fictional range)
    assert "542-11-9087" in joined  # fake SSN
    assert "Lane" in joined  # street address


def test_prompt_collections_are_populated():
    for collection in (
        samples.COMPLETION_PROMPTS,
        samples.IMAGE_GEN_PROMPTS,
        samples.VIDEO_GEN_PROMPTS,
        samples.EMBED_TEXTS,
        samples.TTS_SAMPLES,
    ):
        assert collection
        assert all(isinstance(item, str) and item for item in collection)
