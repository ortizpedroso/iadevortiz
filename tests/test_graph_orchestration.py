"""Testes do grafo DAG, orquestrador topológico e ast_parser."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pkf.utils.ast_parser import extract_imports
from pkf.workflow.orchestrator import run_build_dag
from pkf.workflow.planner import BuildTask, plan_build
from pkf.workflow.task_graph import dag_payload_from_tasks, ready_tasks, topological_layers
from pkf.workflow.tasks import TaskTracker


def test_dag_payload_includes_depends_on(tmp_path):
    tasks = plan_build(
        tmp_path,
        None,
    )
    payload = dag_payload_from_tasks(tasks)
    assert payload["format"] == "dag_v1"
    assert payload["nodes"]
    for node in payload["nodes"]:
        assert "depends_on" in node
        assert "task_id" in node


def test_topological_layers_respects_dependencies():
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
    layers = topological_layers(tasks)
    assert len(layers) == 2
    first = {t.task_id for t in layers[0]}
    assert first == {"backend", "logic"}
    assert layers[1][0].task_id == "frontend"


def test_ready_tasks_waits_for_dependencies():
    tasks = [
        BuildTask(agent="backend", node_id="backend", task_id="backend", instruction="a", depends_on=[]),
        BuildTask(agent="frontend", node_id="frontend", task_id="frontend", instruction="b", depends_on=["backend"]),
    ]
    ready = ready_tasks(tasks, completed=set())
    assert [t.task_id for t in ready] == ["backend"]
    ready2 = ready_tasks(tasks, completed={"backend"})
    assert [t.task_id for t in ready2] == ["frontend"]


@pytest.mark.asyncio
async def test_orchestrator_dag_does_not_run_before_deps(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    order: list[str] = []
    gate = asyncio.Event()

    async def backend_process(_instruction: str) -> str:
        order.append("backend")
        gate.set()
        return "ok"

    async def frontend_process(_instruction: str) -> str:
        order.append("frontend")
        await gate.wait()
        return "ok"

    router = MagicMock()
    router.ui_mode = False
    router.provider_name = "test"
    router.model_to_use = "m"
    router.workspace = MagicMock()
    router.workspace.root = tmp_path
    router.db = None
    router.emit = AsyncMock()
    router.emit_task_tree = AsyncMock()
    router.bind_agent_provider = MagicMock()

    backend = MagicMock()
    backend.model = "m"
    backend.process = AsyncMock(side_effect=backend_process)
    frontend = MagicMock()
    frontend.model = "m"
    frontend.process = AsyncMock(side_effect=frontend_process)
    router.agents = {"backend": backend, "frontend": frontend}

    tasks = [
        BuildTask(agent="backend", node_id="backend", task_id="backend", instruction="api", depends_on=[]),
        BuildTask(
            agent="frontend",
            node_id="frontend",
            task_id="frontend",
            instruction="ui",
            depends_on=["backend"],
        ),
    ]
    tracker = TaskTracker(tmp_path)
    await run_build_dag(router, tasks, tracker)

    assert order.index("backend") < order.index("frontend")
    frontend.process.assert_awaited_once()
    backend.process.assert_awaited_once()


def test_ast_parser_extracts_imports():
    source = """
import os
from pathlib import Path
from pkf.workflow import planner
"""
    imports = extract_imports(source)
    assert "os" in imports
    assert "pathlib" in imports
    assert "pkf" in imports


def test_plan_build_dag_topology(tmp_path):
    from pkf.spec.document import SpecDocument
    from pkf.spec.store import save_spec_document

    doc = SpecDocument(
        title="App",
        body="# App\n\n- API REST com FastAPI\n- Interface React",
        status="approved",
    )
    save_spec_document(tmp_path, "app", doc)
    tasks = plan_build(tmp_path, "app")
    backend = next(t for t in tasks if t.agent == "backend")
    frontend = next(t for t in tasks if t.agent == "frontend")
    assert backend.depends_on == []
    assert "backend" in frontend.depends_on
