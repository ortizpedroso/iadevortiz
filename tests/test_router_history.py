"""Router chat history restore after library navigation."""

from unittest.mock import MagicMock

import pytest

from pkf.provider_pool import ProviderPool, ProviderSlot
from pkf.router import Router
from pkf.workspace import Workspace


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


def test_restore_chat_history_seeds_active_agent(router: Router):
    router._register_core_agents()
    router.cycle.last_agent = "generalista"
    messages = [
        {"role": "user", "content": "primeira"},
        {"role": "assistant", "content": "resposta"},
        {"role": "user", "content": "segunda"},
    ]
    router.restore_chat_history(messages)
    agent = router.agents["generalista"]
    roles = [m["role"] for m in agent.messages]
    assert roles.count("user") == 2
    assert roles[-1] == "user"
    assert agent.messages[-1]["content"] == "segunda"
    architect_users = [m for m in router.agents["architect"].messages if m["role"] == "user"]
    assert architect_users == []
