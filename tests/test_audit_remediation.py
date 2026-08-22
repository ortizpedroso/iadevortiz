"""Testes da remediação AUD-001..AUD-008 (specs/remediacao-auditoria-agentes.md)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from pkf.agents.compact import compact_messages_llm
from pkf.memory.store import MemoryStore
from pkf.provider_pool import ProviderPool, ProviderSlot
from pkf.router import Router
from pkf.tools.impl import write_file
from pkf.workflow.handoff import handoff_context_for_deps, load_handoffs, save_handoff
from pkf.workflow.orchestrator import run_build_dag
from pkf.workflow.planner import BuildTask
from pkf.workflow.task_graph import DagValidationError, validate_dag
from pkf.workflow.tasks import TaskTracker
from pkf.workspace import Workspace


def _mock_router(tmp_path: Path) -> MagicMock:
    router = MagicMock()
    router.ui_mode = False
    router.provider_name = "test"
    router.model_to_use = "m"
    router.workspace = Workspace(tmp_path)
    router.db = None
    router.emit = AsyncMock()
    router.emit_task_tree = AsyncMock()
    router.bind_agent_provider = MagicMock()
    return router


@pytest.mark.asyncio
async def test_dag_blocks_frontend_when_backend_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    router = _mock_router(tmp_path)
    frontend = MagicMock(model="m", process=AsyncMock(return_value="fe ok"))
    router.agents = {
        "backend": MagicMock(
            model="m",
            process=AsyncMock(side_effect=RuntimeError("simulated backend failure")),
        ),
        "logic": MagicMock(model="m", process=AsyncMock(return_value="logic ok")),
        "frontend": frontend,
    }
    tasks = [
        BuildTask(agent="backend", node_id="backend", task_id="backend", instruction="api", depends_on=[]),
        BuildTask(agent="logic", node_id="logic", task_id="logic", instruction="rules", depends_on=[]),
        BuildTask(
            agent="frontend",
            node_id="frontend",
            task_id="frontend",
            instruction="ui",
            depends_on=["backend", "logic"],
        ),
    ]
    results = await run_build_dag(router, tasks, TaskTracker(tmp_path))
    frontend.process.assert_not_awaited()
    skipped = [r for _, r in results if r.startswith("Pulado:")]
    assert skipped
    assert any("backend" in s for s in skipped)


@pytest.mark.asyncio
async def test_handoff_artifacts_from_recorded_changes(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    router = _mock_router(tmp_path)

    async def backend_process(_instruction: str) -> str:
        write_file(router.workspace, "api.py", "print('api')\n")
        return "api criada"

    router.agents = {
        "backend": MagicMock(model="m", process=AsyncMock(side_effect=backend_process)),
    }
    tasks = [
        BuildTask(agent="backend", node_id="backend", task_id="backend", instruction="api", depends_on=[]),
    ]
    await run_build_dag(router, tasks, TaskTracker(tmp_path))
    handoffs = load_handoffs(tmp_path)
    assert handoffs["backend"]["artifacts"]
    assert "api.py" in handoffs["backend"]["artifacts"]


def test_router_boot_does_not_create_all_memory_agents(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    store = MemoryStore(tmp_path)
    for i in range(120):
        store.register(f"mem_{i}", f"summary projeto cardápio digital tema {i}")
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
    router = Router("mock", Workspace(tmp_path), ui_mode=True, client=MagicMock(), provider_pool=pool)
    mem_agents = [k for k in router.agents if k.startswith("mem_")]
    assert len(mem_agents) == 0


def test_memory_store_enforces_max_entries(tmp_path, monkeypatch):
    monkeypatch.setattr("pkf.memory.store.MEMORY_MAX_ENTRIES", 5)
    store = MemoryStore(tmp_path)
    for i in range(10):
        store.register(f"agent_{i}", f"resumo {i} cardápio vitrine modal")
    assert len(store.index) == 5
    assert "agent_0" not in store.index
    assert "agent_9" in store.index


def test_dag_cycle_raises_validation_error():
    tasks = [
        BuildTask(agent="a", node_id="a", task_id="a", instruction="x", depends_on=["b"]),
        BuildTask(agent="b", node_id="b", task_id="b", instruction="y", depends_on=["a"]),
    ]
    with pytest.raises(DagValidationError, match="Ciclo detectado"):
        validate_dag(tasks)


@pytest.mark.asyncio
async def test_run_build_dag_rejects_cycle(tmp_path):
    router = _mock_router(tmp_path)
    router.agents = {
        "a": MagicMock(model="m", process=AsyncMock(return_value="ok")),
        "b": MagicMock(model="m", process=AsyncMock(return_value="ok")),
    }
    tasks = [
        BuildTask(agent="a", node_id="a", task_id="a", instruction="x", depends_on=["b"]),
        BuildTask(agent="b", node_id="b", task_id="b", instruction="y", depends_on=["a"]),
    ]
    with pytest.raises(DagValidationError):
        await run_build_dag(router, tasks, TaskTracker(tmp_path))


def test_failed_handoff_not_injected_to_dependents(tmp_path):
    save_handoff(
        tmp_path,
        "backend",
        agent="backend",
        summary="falhou",
        artifacts=[],
        status="failed",
    )
    save_handoff(
        tmp_path,
        "logic",
        agent="logic",
        summary="ok logic",
        artifacts=["logic.py"],
        status="ok",
    )
    ctx = handoff_context_for_deps(tmp_path, ["backend", "logic"])
    assert "falhou" not in ctx
    assert "logic.py" in ctx


@pytest.mark.asyncio
async def test_compact_llm_includes_recent_file_changes(tmp_path):
    from pkf.workspace_index import record_change

    ws = Workspace(tmp_path)
    record_change(ws, "src/app.py", "create", "x")
    captured: list[str] = []

    async def fake_create(**kwargs):
        captured.append(kwargs["messages"][-1]["content"])
        return MagicMock(choices=[MagicMock(message=MagicMock(content="## Objetivo\nx"))])

    client = MagicMock()
    client.chat.completions.create = fake_create
    msgs = [{"role": "system", "content": "sys"}] + [
        {"role": "user", "content": f"msg {i}"} for i in range(25)
    ]
    await compact_messages_llm(msgs, "model", client, workspace_root=tmp_path)
    assert captured
    assert "src/app.py" in captured[0]
    assert "verificados" in captured[0].lower()
