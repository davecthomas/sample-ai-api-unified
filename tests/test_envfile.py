"""envfile round-trips keys through .env and os.environ."""

import os

import pytest

from sample_ai_api_unified import envfile, paths


@pytest.fixture()
def temp_env(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(paths, "ENV_PATH", env_path)
    monkeypatch.setattr(envfile.paths, "ENV_PATH", env_path)
    return env_path


def test_set_env_values_persists_and_applies(temp_env, monkeypatch):
    monkeypatch.delenv("SAMPLE_TEST_KEY", raising=False)
    envfile.set_env_values({"SAMPLE_TEST_KEY": "abc123"})
    assert os.environ["SAMPLE_TEST_KEY"] == "abc123"
    assert "SAMPLE_TEST_KEY=abc123" in temp_env.read_text()


def test_set_env_values_preserves_other_keys(temp_env):
    temp_env.write_text("KEEP_ME=original\n")
    envfile.set_env_values({"NEW_KEY": "value"})
    content = temp_env.read_text()
    assert "KEEP_ME=original" in content
    assert "NEW_KEY=value" in content


def test_set_env_values_updates_existing_key(temp_env, monkeypatch):
    temp_env.write_text("SAMPLE_TEST_KEY=old\n")
    envfile.set_env_values({"SAMPLE_TEST_KEY": "new"})
    content = temp_env.read_text()
    assert content.count("SAMPLE_TEST_KEY") == 1
    assert "SAMPLE_TEST_KEY=new" in content


def test_unset_env_value(temp_env, monkeypatch):
    temp_env.write_text("DROP_ME=x\nKEEP_ME=y\n")
    monkeypatch.setenv("DROP_ME", "x")
    envfile.unset_env_value("DROP_ME")
    assert "DROP_ME" not in temp_env.read_text()
    assert "KEEP_ME=y" in temp_env.read_text()
    assert "DROP_ME" not in os.environ


def test_ensure_env_file_falls_back_to_template(temp_env, monkeypatch, tmp_path):
    monkeypatch.setattr(envfile.paths, "LOCAL_LIBRARY_DIR", tmp_path / "nowhere")
    template = tmp_path / "env_template"
    template.write_text("FROM_TEMPLATE=1\n")
    monkeypatch.setattr(envfile.paths, "ENV_TEMPLATE_PATH", template)
    envfile.ensure_env_file()
    assert "FROM_TEMPLATE=1" in temp_env.read_text()


def test_ensure_env_file_prefers_library_copy(temp_env, monkeypatch, tmp_path):
    library_dir = tmp_path / "lib"
    library_dir.mkdir()
    (library_dir / ".env").write_text("FROM_LIBRARY=1\n")
    monkeypatch.setattr(envfile.paths, "LOCAL_LIBRARY_DIR", library_dir)
    envfile.ensure_env_file()
    assert "FROM_LIBRARY=1" in temp_env.read_text()
