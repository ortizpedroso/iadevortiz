"""Tests for OpenAI model defaults and VPS env migration."""

from pathlib import Path

from pkf.config import providers


def test_openai_default_model_when_env_unset(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    cfg = providers()["openai"]
    assert cfg.model == "gpt-4o-mini"


def test_set_env_keys_migrates_retired_openai_models(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("OPENAI_MODEL=gpt-4.1-mini\nGROQ_API_KEY=test\n", encoding="utf-8")

    script = Path(__file__).resolve().parents[1] / "deploy" / "hostinger" / "set-env-keys.sh"
    text = script.read_text(encoding="utf-8")
    assert "migrate_openai_model" in text
    assert 'gpt-4.1-mini|gpt-4.1-mini-*' in text or "gpt-4.1-mini" in text
    assert "gpt-4o-mini" in text
    assert "OPENAI_IN_POOL" in text
