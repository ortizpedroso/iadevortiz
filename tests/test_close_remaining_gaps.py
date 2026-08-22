"""Testes das 4 tarefas — fechar lacunas (handoff+resume, consulta barata, Média, TaskTree)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from pkf.tools.impl import get_prior_phase_response
from pkf.workflow.build_results import load_build_results, save_build_result
from pkf.workflow.handoff import (
    MAX_SUMMARY,
    handoff_context_for_deps,
    load_handoffs,
    resume_handoff_summary,
    save_handoff,
)
from pkf.workflow.orchestrator import run_build_dag
from pkf.workflow.planner import BuildTask
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
async def test_resume_build_injects_persisted_handoffs(tmp_path, monkeypatch):
    """Tarefa 1: retomada usa handoffs salvos das tarefas já concluídas."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    router = _mock_router(tmp_path)

    long_backend = "BACKEND_FULL_" + ("x" * 3000)
    long_logic = "LOGIC_FULL_" + ("y" * 3000)
    captured: list[str] = []

    async def backend_process(_instruction: str) -> str:
        return long_backend

    async def logic_process(_instruction: str) -> str:
        return long_logic

    async def frontend_process(instruction: str) -> str:
        captured.append(instruction)
        return "fe ok"

    router.agents = {
        "backend": MagicMock(model="m", process=AsyncMock(side_effect=backend_process)),
        "logic": MagicMock(model="m", process=AsyncMock(side_effect=logic_process)),
        "frontend": MagicMock(model="m", process=AsyncMock(side_effect=frontend_process)),
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
        BuildTask(agent="tester", node_id="tester", task_id="tester", instruction="tests", depends_on=["frontend"]),
    ]

    # Fase 1: conclui backend e logic (simula interrupção antes de frontend)
    await run_build_dag(
        router,
        tasks,
        TaskTracker(tmp_path),
        only_agents={"backend", "logic"},
    )
    handoffs = load_handoffs(tmp_path)
    assert "backend" in handoffs and "logic" in handoffs

    # Fase 2: retoma — frontend deve receber handoffs truncados (2000) das duas deps
    await run_build_dag(
        router,
        tasks,
        TaskTracker(tmp_path),
        only_agents={"frontend"},
        initial_completed={"backend", "logic"},
    )
    assert captured
    payload = captured[0]
    assert "Contexto de handoff" in payload
    assert "BACKEND_FULL_" in payload
    assert "LOGIC_FULL_" in payload
    assert handoff_context_for_deps(tmp_path, ["backend", "logic"]) in payload


def test_resume_handoff_summary_lists_completed(tmp_path):
    save_handoff(tmp_path, "backend", agent="backend", summary="api pronta", artifacts=["api.py"])
    save_handoff(tmp_path, "logic", agent="logic", summary="regras ok", artifacts=["logic.py"])
    summary = resume_handoff_summary(tmp_path, ["backend", "logic"])
    assert "backend" in summary
    assert "logic" in summary
    assert "api pronta" in summary


def test_get_prior_phase_response_returns_full_not_handoff_truncated(tmp_path):
    """Tarefa 2: ferramenta retorna texto integral, não o resumo de 2000 chars."""
    full_text = "RESPOSTA_INTEGRAL_" + ("Z" * 4500)
    save_build_result(tmp_path, "backend", agent="backend", response=full_text)
    save_handoff(tmp_path, "backend", agent="backend", summary=full_text[:MAX_SUMMARY])

    ws = Workspace(tmp_path)
    out = get_prior_phase_response(ws, task_id="backend")
    assert "RESPOSTA_INTEGRAL_" in out
    assert "Z" * 4000 in out
    assert len(out) > MAX_SUMMARY


def test_build_results_enforces_max_entries(tmp_path, monkeypatch):
    monkeypatch.setattr("pkf.workflow.build_results.BUILD_RESPONSE_MAX_ENTRIES", 3)
    for i in range(5):
        save_build_result(tmp_path, f"t{i}", agent="backend", response=f"resp {i}")
    store = load_build_results(tmp_path)
    assert len(store) == 3
    assert "t0" not in store
    assert "t4" in store


def test_handoff_truncates_at_max_summary(tmp_path):
    """AUD-005: truncamento de handoff em 2000 chars."""
    long_text = "A" * 5000
    save_handoff(tmp_path, "backend", agent="backend", summary=long_text)
    entry = load_handoffs(tmp_path)["backend"]
    assert len(entry["summary"]) == MAX_SUMMARY


@pytest.mark.asyncio
async def test_skipped_tasks_mark_tracker_status(tmp_path, monkeypatch):
    """Tarefa 4 / AUD-001: tarefas puladas aparecem com status skipped na árvore."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    router = _mock_router(tmp_path)
    tracker = TaskTracker(tmp_path)
    tracker.reset_for_build("app", ["backend", "logic", "frontend"])
    router.agents = {
        "backend": MagicMock(
            model="m",
            process=AsyncMock(side_effect=RuntimeError("fail")),
        ),
        "logic": MagicMock(model="m", process=AsyncMock(return_value="ok")),
        "frontend": MagicMock(model="m", process=AsyncMock(return_value="fe")),
    }
    tasks = [
        BuildTask(agent="backend", node_id="backend", task_id="backend", instruction="api", depends_on=[]),
        BuildTask(agent="logic", node_id="logic", task_id="logic", instruction="rules", depends_on=[]),
        BuildTask(
            agent="frontend",
            node_id="frontend",
            task_id="frontend",
            instruction="ui",
            depends_on=["backend"],
        ),
    ]
    await run_build_dag(router, tasks, tracker)
    statuses = tracker.agent_statuses()
    assert statuses["frontend"] == "skipped"
    impl = next(c for c in tracker.tree.children if c.id == "T2")
    fe_node = next(c for c in impl.children if "frontend" in c.title.lower())
    assert "pulado" in fe_node.detail.lower()


def test_mark_resume_agents_sets_detail(tmp_path):
    tracker = TaskTracker(tmp_path)
    tracker.reset_for_build("demo", ["backend", "frontend"])
    tracker.set_child_status("backend", "done")
    tracker.mark_resume_agents({"backend"})
    impl = next(c for c in tracker.tree.children if c.id == "T2")
    be_node = next(c for c in impl.children if "backend" in c.title.lower())
    assert be_node.detail
    assert "retomado" in be_node.detail.lower()
    assert "handoff" in be_node.detail.lower()


def test_task_node_serializes_detail(tmp_path):
    tracker = TaskTracker(tmp_path)
    tracker.reset_for_build("demo", ["backend"])
    tracker.set_child_status("backend", "skipped", detail="pulado — dependência falhou")
    payload = tracker.to_list()[0]
    impl = next(c for c in payload["children"] if c["id"] == "T2")
    be = impl["children"][0]
    assert be["status"] == "skipped"
    assert "pulado" in be["detail"]
