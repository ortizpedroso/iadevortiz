from pkf.config import fallback_model_on_not_found


def test_gemini_fallback_chain_from_retired_model():
    base = "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert fallback_model_on_not_found("gemini-2.0-flash", base) == "gemini-2.5-flash"
    assert fallback_model_on_not_found("gemini-2.5-flash", base) == "gemini-3.6-flash"
    assert fallback_model_on_not_found("gemini-3.6-flash", base) == "gemini-3.5-flash-lite"


def test_gemini_default_model(monkeypatch):
    from pkf.config import providers

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    cfg = providers()["gemini"]
    assert cfg.model == "gemini-2.5-flash"
