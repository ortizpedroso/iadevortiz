from pkf.errors import explain_provider_error


def test_ollama_connection_message():
    text = explain_provider_error("ollama", Exception("Connection error."))
    assert "Ollama" in text
    assert "localhost:11434" in text


def test_openai_model_not_found_message():
    exc = Exception(
        "Error code: 404 - {'error': {'message': \"The model 'gpt-4o-mini' does not exist\", "
        "'code': 'model_not_found'}}"
    )
    text = explain_provider_error("openai", exc)
    assert "modelo configurado" in text.lower() or "model" in text.lower()
    assert "OPENAI_MODEL" in text


def test_router_only_rate_limit_message(monkeypatch):
    monkeypatch.setenv("PKF_ROUTER_ONLY", "1")
    text = explain_provider_error("ninerouter", Exception("Error 429 rate limit exceeded"))
    assert "limite" in text.lower()
    assert "Groq" not in text
    assert "Gemini" not in text
    assert "alterna modelos" in text.lower()


def test_router_only_gateway_model_rejection_message(monkeypatch):
    from openai import APIStatusError

    monkeypatch.setenv("PKF_ROUTER_ONLY", "1")

    exc = APIStatusError.__new__(APIStatusError)
    exc.status_code = 400
    Exception.__init__(exc, "Invalid auto prefix format for auto/free")

    text = explain_provider_error("ninerouter", exc)
    assert "auto/free" in text
    assert "oc/big-pickle" in text
