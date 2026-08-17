"""Router chat history restore after library navigation."""

from unittest.mock import MagicMock

import pytest

from pkf.router import Router
from pkf.workspace import Workspace


@pytest.fixture
def router(tmp_path):
    ws = Workspace(tmp_path)
    return Router("mock", ws, ui_mode=True, client=MagicMock())


def test_restore_chat_history_seeds_agents(router: Router):
    router._register_core_agents()
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
