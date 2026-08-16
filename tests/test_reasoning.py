from pkf.config import model_for_task, providers
from pkf.deepseek import format_file_context, format_search_results, web_search_format
from pkf.reasoning import (
    adapt_messages_for_reasoning,
    agent_uses_reasoning,
    completion_params_for_model,
    is_reasoning_model,
    parse_thinking,
    prepare_messages_for_api,
)


def test_is_reasoning_model():
    assert is_reasoning_model("deepseek-reasoner")
    assert is_reasoning_model("deepseek-ai/DeepSeek-R1-Distill-Qwen-32B")
    assert not is_reasoning_model("deepseek-chat")


def test_parse_thinking_strips_block():
    open_tag = "<" + "think" + ">"
    close_tag = "</" + "think" + ">"
    raw = f"{open_tag}\nplanejar arquitetura\n{close_tag}\n\nResposta final."
    thinking, answer = parse_thinking(raw)
    assert "planejar" in thinking
    assert answer == "Resposta final."


def test_parse_thinking_reasoning_content_field():
    thinking, answer = parse_thinking("Resposta.", "passo interno")
    assert thinking == "passo interno"
    assert answer == "Resposta."


def test_adapt_messages_merges_system_into_user():
    messages = [
        {"role": "system", "content": "Você é arquiteto."},
        {"role": "user", "content": "Crie uma API."},
    ]
    adapted = adapt_messages_for_reasoning(messages)
    assert len(adapted) == 1
    assert adapted[0]["role"] == "user"
    assert "Você é arquiteto." in adapted[0]["content"]
    assert "Crie uma API." in adapted[0]["content"]


def test_completion_params_reasoner_temperature():
    params = completion_params_for_model("deepseek-reasoner")
    assert params["temperature"] == 0.6


def test_prepare_messages_skips_non_reasoning_agent(monkeypatch):
    monkeypatch.delenv("PKF_REASONING_MODEL", raising=False)
    messages = [{"role": "system", "content": "x"}, {"role": "user", "content": "y"}]
    out = prepare_messages_for_api(messages, "llama-3.1-8b-instant", "frontend")
    assert out == messages


def test_model_for_task_uses_reasoner_when_deepseek_configured(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("PKF_ARCHITECT_MODEL", raising=False)
    model = model_for_task("architect", "llama-3.1-8b-instant")
    assert model == "deepseek-reasoner"


def test_deepseek_provider_registered(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    cfg = providers()["deepseek"]
    assert cfg.base_url.endswith("deepseek.com")
    assert cfg.model == "deepseek-chat"


def test_deepseek_search_format():
    results = [{"title": "FastAPI", "url": "https://fastapi.tiangolo.com", "snippet": "Python web"}]
    text = format_search_results("fastapi", results, language="pt")
    assert "[webpage 1 begin]" in text
    assert "FastAPI" in text
    assert "fastapi" in text.lower()


def test_file_context_template():
    text = format_file_context("main.py", "print('hi')", "Explique o arquivo.")
    assert "[file name]: main.py" in text
    assert "Explique o arquivo." in text


def test_web_search_format_env(monkeypatch):
    monkeypatch.setenv("PKF_WEB_SEARCH_FORMAT", "deepseek")
    assert web_search_format() == "deepseek"


def test_agent_uses_reasoning_with_explicit_model(monkeypatch):
    monkeypatch.setenv("PKF_REASONING_MODEL", "deepseek-reasoner")
    assert agent_uses_reasoning("frontend", "deepseek-reasoner")
    monkeypatch.delenv("PKF_REASONING_MODEL", raising=False)
    assert agent_uses_reasoning("architect", "deepseek-reasoner")
