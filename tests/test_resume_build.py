from pkf.classifier import classify_intent
from pkf.tools.impl import get_build_status
from pkf.workflow.tasks import TaskTracker


def test_resume_intent_routes_to_generalista():
    intent = classify_intent("continue de onde parou")
    assert intent.kind == "resume_request"
    assert intent.agent == "generalista"
    assert intent.source == "keywords"


def test_retomar_build_intent():
    intent = classify_intent("retomar o build")
    assert intent.kind == "resume_request"


def test_prepare_for_build_resume_preserves_done(tmp_path):
    tracker = TaskTracker(tmp_path)
    tracker.reset_for_build("demo-spec", ["backend", "frontend", "logic"])
    tracker.set_child_status("backend", "done")
    tracker.set_child_status("logic", "done")

    done = tracker.prepare_for_build("demo-spec", ["backend", "frontend", "logic"], resume=True)

    assert done == {"backend", "logic"}
    statuses = tracker.agent_statuses()
    assert statuses["backend"] == "done"
    assert statuses["logic"] == "done"
    assert statuses["frontend"] == "pending"


def test_prepare_for_build_resume_resets_failed_to_pending(tmp_path):
    tracker = TaskTracker(tmp_path)
    tracker.reset_for_build("demo-spec", ["backend", "frontend"])
    tracker.set_child_status("backend", "failed")

    tracker.prepare_for_build("demo-spec", ["backend", "frontend"], resume=True)

    assert tracker.agent_statuses()["backend"] == "pending"


def test_prepare_for_build_fresh_when_spec_differs(tmp_path):
    tracker = TaskTracker(tmp_path)
    tracker.reset_for_build("old-spec", ["backend"])
    tracker.set_child_status("backend", "done")

    done = tracker.prepare_for_build("new-spec", ["backend", "frontend"], resume=True)

    assert done == set()
    assert tracker.agent_statuses() == {"backend": "pending", "frontend": "pending"}


def test_get_build_status_includes_cycle_and_tasks(tmp_path):
    from pkf.workflow.cycle import DevCycle
    from pkf.workspace import Workspace

    ws = Workspace(tmp_path)
    cycle = DevCycle(phase="BUILD", active_spec="app", spec_status="approved")
    cycle.persist(tmp_path)
    tracker = TaskTracker(tmp_path)
    tracker.reset_for_build("app", ["frontend"])

    out = get_build_status(ws)

    assert "Fase: BUILD" in out
    assert "app" in out
    assert "Árvore de tarefas" in out
    assert "frontend" in out
