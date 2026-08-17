from pkf.config import default_fallback, default_provider


def test_production_defaults_to_ninerouter_when_url_set(monkeypatch):
    monkeypatch.setenv("PKF_ENV", "production")
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("NINEROUTER_KEY", "sk-test")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    monkeypatch.setattr("pkf.ninerouter.ninerouter_health", lambda: (True, "ok"))
    assert default_provider() == "ninerouter"


def test_production_defaults_to_groq_when_key_set(monkeypatch):
    monkeypatch.setenv("PKF_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    assert default_provider() == "groq"
