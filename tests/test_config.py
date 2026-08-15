from pkf.config import default_fallback, default_provider


def test_production_defaults_to_kimi_when_key_set(monkeypatch):
    monkeypatch.setenv("PKF_ENV", "production")
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    assert default_provider() == "kimi"
    assert default_fallback("kimi") is None
