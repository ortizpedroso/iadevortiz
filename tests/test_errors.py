from pkf.errors import explain_provider_error


def test_ollama_connection_message():
    text = explain_provider_error("ollama", Exception("Connection error."))
    assert "Ollama" in text
    assert "localhost:11434" in text
