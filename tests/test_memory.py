from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pkf.config import RELEVANCE_THRESHOLD
from pkf.memory.store import MemoryStore, _memory_tokens
from pkf.provider_pool import ProviderPool, ProviderSlot
from pkf.router import Router
from pkf.workspace import Workspace


def test_memory_register_and_find(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.register("memoria_frontend_1-12", "decisão de usar react no botão da tela de login")
    name, score = store.find("como ficou o botão da tela de login?", RELEVANCE_THRESHOLD)
    assert name == "memoria_frontend_1-12"
    assert score >= int(RELEVANCE_THRESHOLD * 100)


def test_memory_ignores_generic_domain_words(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.register(
        "memoria_cardapio_antigo",
        "cardápio digital whitelabel vitrine pública modal detalhes backend modelos prontos",
    )
    name, _score = store.find("Quero desenvolver um sistema", RELEVANCE_THRESHOLD)
    assert name is None


def test_memory_does_not_match_similar_projects_with_shallow_overlap(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.register(
        "memoria_cardapio_a",
        "cardápio digital whitelabel vitrine pública modal detalhes backend modelos",
    )
    store.register(
        "memoria_cardapio_b",
        "cardápio digital delivery integração pagamento checkout",
    )
    name, _score = store.find("Quero um cardápio digital", RELEVANCE_THRESHOLD)
    assert name is None


def test_memory_tokens_drop_domain_stopwords():
    tokens = _memory_tokens("Quero desenvolver um sistema de cardápio digital")
    assert "quero" not in tokens
    assert "desenvolver" not in tokens
    assert "sistema" not in tokens
    assert "cardápio" in tokens


@pytest.fixture
def router(tmp_path):
    ws = Workspace(tmp_path)
    pool = ProviderPool(
        slots=[
            ProviderSlot(
                slot_id="mock-1",
                provider="mock",
                api_key="test-key",
                tier="free",
                model="mock-model",
            )
        ],
    )
    return Router("mock", ws, ui_mode=True, client=MagicMock(), provider_pool=pool)


def test_memory_agent_has_read_tools_and_workspace_check_prompt(tmp_path: Path, router: Router):
    summary = "cardápio digital whitelabel vitrine modal backend modelos prontos"
    router.memory.register("memoria_cardapio_antigo", summary)
    router._restore_memory_agents()
    agent = router.agents["memoria_cardapio_antigo"]
    assert agent.supports_tools is True
    assert agent.tools is not None
    assert set(agent.tools.tool_names) == {
        "project_context",
        "list_dir",
        "read_file",
        "search_code",
    }
    prompt = agent.messages[0]["content"]
    assert "conversa ANTERIOR" in prompt or "conversa anterior" in prompt.lower()
    assert "list_dir" in prompt
    assert "não corresponder ao resumo" in prompt.lower() or "nao corresponder ao resumo" in prompt.lower()


def test_memory_agent_prompt_warns_when_project_empty(tmp_path: Path, router: Router):
    router.memory.register(
        "memoria_cardapio_vazio",
        "vitrine pública, modal de detalhes, backend com modelos já prontos",
    )
    router._restore_memory_agents()
    prompt = router.agents["memoria_cardapio_vazio"].messages[0]["content"]
    assert "diretório do projeto estiver vazio" in prompt.lower() or "diretorio do projeto estiver vazio" in prompt.lower()
    assert "sem projeto ativo" in router.workspace.scan_summary().lower()
