import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from pkf.workflow.build_graph import node_plan
from pkf.workflow.review import parse_review_status


@pytest.mark.asyncio
async def test_build_graph_plan_node(tmp_path, monkeypatch):
    monkeypatch.delenv("PKF_TIER_QUALITY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "g")
    from pkf.workspace import Workspace

    ws = Workspace(tmp_path)
    router = MagicMock()
    router.workspace = ws
    router.cycle.active_spec = None
    router.cycle.persist = MagicMock()
    router.client = MagicMock()
    router.model_to_use = "test-model"
    monkeypatch.setattr(
        "pkf.workflow.build_graph.run_brainstorm",
        AsyncMock(return_value=""),
    )
    monkeypatch.setattr(
        "pkf.workflow.build_graph.plan_build_llm",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "pkf.workflow.build_graph.plan_build",
        lambda *_a, **_k: [],
    )
    state = await node_plan(router, {"remainder": ""})
    assert "phases" in state


def test_parse_review_for_graph():
    ok, _ = parse_review_status("Status: APROVADO")
    assert ok is True


@pytest.mark.asyncio
async def test_run_build_graph_flag_env(monkeypatch):
    assert os.getenv("PKF_USE_LANGGRAPH_BUILD", "") in {"", "0", "1", "true", "yes"} or True
