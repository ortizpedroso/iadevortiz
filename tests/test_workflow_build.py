from pkf.workflow.planner import (
    BuildTask,
    group_tasks_into_phases,
    plan_build,
    plan_fix_tasks,
)
from pkf.workflow.review import parse_review_status


def test_group_tasks_into_phases_order(tmp_path):
    tasks = plan_build(tmp_path, None)
    phases = group_tasks_into_phases(tasks)
    assert phases
    agents_flat = [t.agent for phase in phases for t in phase]
    assert "frontend" in agents_flat


def test_phases_backend_before_frontend(tmp_path):
    from pkf.spec.document import SpecDocument
    from pkf.spec.store import save_spec_document

    doc = SpecDocument(
        title="App",
        body="# App\n\n- API REST com FastAPI\n- Interface React",
        status="approved",
        suggested_stack={"frontend": "React", "backend": "FastAPI"},
    )
    save_spec_document(tmp_path, "app", doc)
    tasks = plan_build(tmp_path, "app")
    phases = group_tasks_into_phases(tasks)
    order = [t.agent for phase in phases for t in phase]
    assert order.index("backend") < order.index("frontend")


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
