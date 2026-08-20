from pkf.config import providers


def test_openai_default_model_when_env_unset(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    cfg = providers()["openai"]
    assert cfg.model == "gpt-4.1-mini"
