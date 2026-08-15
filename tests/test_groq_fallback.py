from pkf.config import fallback_model_on_rate_limit, is_groq_client


def test_groq_fallback_model():
    assert is_groq_client("https://api.groq.com/openai/v1")
    assert (
        fallback_model_on_rate_limit("llama-3.3-70b-versatile", "https://api.groq.com/openai/v1")
        == "llama-3.1-8b-instant"
    )
    assert fallback_model_on_rate_limit("llama-3.1-8b-instant", "https://api.groq.com/openai/v1") is None
