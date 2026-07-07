"""Profile dataclasses render the YAML shape ai-api-unified expects."""

import pytest
import yaml

from sample_ai_api_unified import middleware_profile as mp


def test_default_profile_yaml_shape():
    payload = mp.to_yaml_dict(mp.MiddlewareProfile())
    entries = {entry["name"]: entry for entry in payload["middleware"]}
    assert set(entries) == {"observability", "pii_redaction"}

    observability = entries["observability"]
    assert observability["enabled"] is True
    assert observability["settings"]["direction"] == "input_output"
    assert observability["settings"]["log_level"] == "INFO"
    assert observability["settings"]["token_count_mode"] == "provider_or_estimate"
    # Empty capability selection means "all" and must be omitted entirely.
    assert "capabilities" not in observability["settings"]

    pii = entries["pii_redaction"]
    assert pii["enabled"] is False
    assert pii["settings"]["direction"] == "input_only"
    assert pii["settings"]["detection_profile"] == "balanced"
    # Default profile redacts every entity type, so nothing is allowed through.
    assert pii["settings"]["allowed_entities"] == []


def test_selected_capabilities_are_listed():
    profile = mp.MiddlewareProfile(
        observability=mp.ObservabilityProfile(capabilities=("completions", "tts"))
    )
    payload = mp.to_yaml_dict(profile)
    observability = payload["middleware"][0]
    assert observability["settings"]["capabilities"] == ["completions", "tts"]


def test_write_and_read_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(mp.envfile, "set_env_values", lambda values: None)
    path = tmp_path / "middleware.yaml"
    original = mp.MiddlewareProfile(
        observability=mp.ObservabilityProfile(
            enabled=False,
            direction="input_only",
            log_level="DEBUG",
            capabilities=("embeddings",),
            token_count_mode="none",
            emit_error_events=False,
            emit_cost=True,
        ),
        pii=mp.PiiProfile(
            enabled=True,
            direction="input_output",
            strict_mode=True,
            detection_profile="high_accuracy",
            default_redaction_label="MASKED",
            redact_entities=("EMAIL", "SSN"),
        ),
    )
    mp.write_profile(original, path)
    assert yaml.safe_load(path.read_text())  # valid YAML on disk
    assert mp.read_profile(path) == original


def test_emit_cost_defaults_off_and_lands_in_yaml():
    assert mp.ObservabilityProfile().emit_cost is False  # observe-only opt-in
    data = mp.to_yaml_dict(mp.MiddlewareProfile())
    obs_settings = data["middleware"][0]["settings"]
    assert obs_settings["emit_cost"] is False


def test_read_profile_missing_file_returns_defaults(tmp_path):
    assert mp.read_profile(tmp_path / "absent.yaml") == mp.MiddlewareProfile()


def test_read_profile_bad_yaml_returns_defaults(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("middleware: [unclosed")
    assert mp.read_profile(path) == mp.MiddlewareProfile()


def test_write_profile_sets_config_path_env(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(mp.envfile, "set_env_values", captured.update)
    path = tmp_path / "middleware.yaml"
    mp.write_profile(mp.MiddlewareProfile(), path)
    assert captured == {"AI_MIDDLEWARE_CONFIG_PATH": str(path)}


def test_redact_entities_invert_to_allowed_entities():
    """The library's allowed_entities are categories allowed through UNredacted."""
    profile = mp.MiddlewareProfile(pii=mp.PiiProfile(redact_entities=("EMAIL", "SSN")))
    pii = mp.to_yaml_dict(profile)["middleware"][1]
    assert sorted(pii["settings"]["allowed_entities"]) == sorted(
        set(mp.PII_ENTITIES) - {"EMAIL", "SSN"}
    )


@pytest.mark.parametrize("value", mp.DIRECTIONS)
def test_directions_match_library_contract(value):
    assert value in ("input_only", "output_only", "input_output")


def test_read_profile_tolerates_null_yaml_keys(tmp_path):
    """A present-but-null key (valid YAML the library tolerates) must not crash."""
    path = tmp_path / "middleware.yaml"
    path.write_text(
        "middleware:\n"
        "- name: observability\n"
        "  enabled: true\n"
        "  settings:\n"
        "    capabilities:\n"
        "- name: pii_redaction\n"
        "  enabled: true\n"
        "  settings:\n"
        "    allowed_entities:\n"
    )
    profile = mp.read_profile(path)
    assert profile.observability.capabilities == ()
    assert profile.pii.redact_entities == mp.PII_ENTITIES
