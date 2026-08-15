from pathlib import Path

import pytest

from pkf.graph.project import ProjectGraph
from pkf.tools.impl import edit_file, write_file
from pkf.workflow.planner import plan_build
from pkf.workspace import Workspace


def test_edit_file_replaces_snippet(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(ws, "a.py", "hello world\n")
    result = edit_file(ws, "a.py", "world", "PKF")
    assert "1 substituição" in result
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "hello PKF\n"


def test_project_graph_predefined_and_dynamic(tmp_path: Path):
    graph = ProjectGraph(tmp_path)
    assert "frontend" in graph.nodes
    node = graph.maybe_cluster_labels("frontend", ["a", "b", "c"])
    assert node is not None
    assert node.kind == "dynamic"


def test_plan_build_from_empty_spec(tmp_path: Path):
    tasks = plan_build(tmp_path, None)
    assert len(tasks) >= 1
    assert tasks[0].agent == "frontend"


def test_verify_build_requires_session_changes(tmp_path: Path):
    from pkf.workspace_index import begin_build_session, verify_workspace_files

    ws = Workspace(tmp_path)
    assert verify_workspace_files(ws)["ok"] is False
    begin_build_session(ws)
    write_file(ws, "app.js", "console.log('ok')")
    result = verify_workspace_files(ws)
    assert result["ok"] is True
    assert "app.js" in result["files"]
