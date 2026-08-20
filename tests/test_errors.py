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
