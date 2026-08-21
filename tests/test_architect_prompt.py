from pkf.agents.prompts import AGENT_PROMPTS


def test_architect_prompt_requires_interview_before_save_spec():
    prompt = AGENT_PROMPTS["architect"]
    assert "NÃO chame save_spec enquanto" in prompt
    assert "UMA pergunta específica por vez" in prompt
    assert "CORRETO:" in prompt
    assert "ERRADO:" in prompt
    assert "Nunca produza uma tabela ou lista numerada de perguntas" in prompt
    assert "sugira você" in prompt
    assert "/spec → /build → /review" in prompt
    assert "web_search" in prompt
    assert "AUTOMATICAMENTE" not in prompt


def test_architect_prompt_allows_direct_spec_when_detailed():
    prompt = AGENT_PROMPTS["architect"]
    assert "informação suficiente numa mensagem" in prompt
    assert "entrevista não é burocracia obrigatória" in prompt
