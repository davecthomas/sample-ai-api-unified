"""Drive the menu-based middleware profile editor end to end via scripted input."""

import pytest
import yaml

from sample_ai_api_unified import middleware_profile as mp


def feed(monkeypatch, lines):
    iterator = iter(lines)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(iterator))


@pytest.fixture()
def editor_env(monkeypatch, tmp_path):
    yaml_path = tmp_path / "middleware.yaml"
    monkeypatch.setattr(mp.paths, "MIDDLEWARE_YAML_PATH", yaml_path)
    written_env = {}
    monkeypatch.setattr(mp.envfile, "set_env_values", written_env.update)
    return yaml_path, written_env


def test_enable_pii_and_save(monkeypatch, editor_env):
    yaml_path, written_env = editor_env
    # editor: 2=PII -> 1=toggle enabled -> 0=done -> 3=save
    feed(monkeypatch, ["2", "1", "0", "3"])
    profile = mp.edit_profile()
    assert profile.pii.enabled is True
    data = yaml.safe_load(yaml_path.read_text())
    pii_entry = next(e for e in data["middleware"] if e["name"] == "pii_redaction")
    assert pii_entry["enabled"] is True
    assert written_env == {"AI_MIDDLEWARE_CONFIG_PATH": str(yaml_path)}


def test_cancel_discards_changes(monkeypatch, editor_env):
    yaml_path, _ = editor_env
    # editor: 2=PII -> 1=toggle enabled -> 0=done -> 0=cancel
    feed(monkeypatch, ["2", "1", "0", "0"])
    profile = mp.edit_profile()
    assert profile.pii.enabled is False  # discarded; fresh read of (missing) file
    assert not yaml_path.exists()


def test_edit_observability_settings(monkeypatch, editor_env):
    yaml_path, _ = editor_env
    # 1=observability -> 4=log level -> 1=DEBUG -> 2=direction -> 1=input_only
    # -> 0=done -> 3=save
    feed(monkeypatch, ["1", "4", "1", "2", "1", "0", "3"])
    profile = mp.edit_profile()
    assert profile.observability.log_level == "DEBUG"
    assert profile.observability.direction == "input_only"


def test_entity_toggle_inverts_into_allowed_entities(monkeypatch, editor_env):
    yaml_path, _ = editor_env
    # 2=PII -> 6=entities -> toggle NAME off (1) -> 0=done -> 0=done -> 3=save
    feed(monkeypatch, ["2", "6", "1", "0", "0", "3"])
    profile = mp.edit_profile()
    assert "NAME" not in profile.pii.redact_entities
    data = yaml.safe_load(yaml_path.read_text())
    pii_entry = next(e for e in data["middleware"] if e["name"] == "pii_redaction")
    assert pii_entry["settings"]["allowed_entities"] == ["NAME"]


def test_existing_profile_reloads_into_editor(monkeypatch, editor_env):
    yaml_path, _ = editor_env
    mp.write_profile(
        mp.MiddlewareProfile(pii=mp.PiiProfile(enabled=True, strict_mode=True)), yaml_path
    )
    # open PII (2), toggle strict off (3), done (0), save (3)
    feed(monkeypatch, ["2", "3", "0", "3"])
    profile = mp.edit_profile()
    assert profile.pii.enabled is True  # preserved from disk
    assert profile.pii.strict_mode is False  # edited
