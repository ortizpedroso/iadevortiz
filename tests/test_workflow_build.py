import pytest

from pkf.workflow.planner import (
    BuildTask,
    group_tasks_into_phases,
    plan_build,
    plan_fix_tasks,
)
from pkf.workflow.review import parse_review_status


def _save_spec(tmp_path, body: str, **stack):
    from pkf.spec.document import SpecDocument
    from pkf.spec.store import save_spec_document

    doc = SpecDocument(
        title="App",
        body=body,
        status="approved",
        suggested_stack=stack or {"frontend": "React", "backend": "FastAPI"},
    )
    save_spec_document(tmp_path, "app", doc)


def test_group_tasks_into_phases_order(tmp_path):
    tasks = plan_build(tmp_path, None)
    phases = group_tasks_into_phases(tasks)
    assert phases
    agents_flat = [t.agent for phase in phases for t in phase]
    assert "frontend" in agents_flat


def test_phases_backend_before_frontend(tmp_path):
    _save_spec(
        tmp_path,
        "# App\n\n- API REST com FastAPI\n- Interface React",
        frontend="React",
        backend="FastAPI",
    )
    tasks = plan_build(tmp_path, "app")
    phases = group_tasks_into_phases(tasks)
    order = [t.agent for phase in phases for t in phase]
    assert order.index("backend") < order.index("frontend")


def test_backend_and_logic_share_same_phase(tmp_path):
    _save_spec(
        tmp_path,
        "# App\n\n- API REST com FastAPI\n- regras de negócio multi-tenant\n- Interface React",
    )
    tasks = plan_build(tmp_path, "app")
    phases = group_tasks_into_phases(tasks)
    first_agents = {t.agent for t in phases[0]}
    assert first_agents == {"backend", "logic"}
    assert len(phases[0]) == 2


def test_backend_only_without_logic_stays_single_task_phase(tmp_path):
    _save_spec(tmp_path, "# App\n\n- API REST com FastAPI\n- Interface React")
    tasks = plan_build(tmp_path, "app")
    phases = group_tasks_into_phases(tasks)
    assert len(phases[0]) == 1
    assert phases[0][0].agent == "backend"
    assert phases[1][0].agent == "frontend"


def test_frontend_and_tester_remain_separate_later_phases(tmp_path):
    _save_spec(
        tmp_path,
        "# App\n\n- API REST\n- regras de negócio\n- Interface React\n- testes pytest",
    )
    tasks = plan_build(tmp_path, "app")
    phases = group_tasks_into_phases(tasks)
    assert len(phases) == 3
    assert {t.agent for t in phases[0]} == {"backend", "logic"}
    assert phases[1][0].agent == "frontend"
    assert phases[2][0].agent == "tester"


def test_parse_review_approved():
    text = """# Review
## Lacunas
(nenhuma)
## Status
APROVADO
"""
    ok, issues = parse_review_status(text)
    assert ok is True
    assert issues == []


def test_parse_review_rejected():
    text = """# Review
## Lacunas
- [ ] Falta index.html
## Status
REPROVADO
"""
    ok, issues = parse_review_status(text)
    assert ok is False
    assert issues


def test_plan_fix_tasks_routes_to_frontend():
    tasks = plan_fix_tasks("demo", ["index.html não encontrado"])
    assert tasks
    assert tasks[0].agent == "frontend"


def test_llm_phases_preserved():
    tasks = [
        BuildTask(agent="frontend", node_id="frontend", instruction="ui", phase=1),
        BuildTask(agent="backend", node_id="backend", instruction="api", phase=0),
    ]
    phases = group_tasks_into_phases(tasks)
    assert phases[0][0].agent == "backend"
    assert phases[1][0].agent == "frontend"


@pytest.mark.asyncio
async def test_run_build_phases_parallel_backend_logic(tmp_path):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from pkf.workflow.orchestrator import run_build_phases
    from pkf.workflow.tasks import TaskTracker

    gate = asyncio.Event()
    in_flight = 0
    max_in_flight = 0

    async def slow_process(_instruction: str) -> str:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await gate.wait()
        in_flight -= 1
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
    backend.process = AsyncMock(side_effect=slow_process)
    logic = MagicMock()
    logic.model = "m"
    logic.process = AsyncMock(side_effect=slow_process)
    router.agents = {"backend": backend, "logic": logic}

    phase_tasks = [
        BuildTask(agent="backend", node_id="backend", task_id="backend", instruction="api", depends_on=[]),
        BuildTask(agent="logic", node_id="logic", task_id="logic", instruction="rules", depends_on=[]),
    ]
    tracker = TaskTracker(tmp_path)

    run_task = asyncio.create_task(run_build_phases(router, [phase_tasks], tracker))
    await asyncio.sleep(0.05)
    assert max_in_flight == 2
    gate.set()
    results = await run_task

    assert len(results) == 2
    assert backend.process.await_count == 1
    assert logic.process.await_count == 1
