import pytest

from pkf.projects.manager import ensure_project
from pkf.web.library import delete_projects_bulk, library_snapshot
from pkf.workspace import Workspace


@pytest.mark.asyncio
async def test_bulk_delete_projects(tmp_path):
    ws = Workspace(tmp_path)
    ensure_project(ws.global_root, "proj-a")
    ensure_project(ws.global_root, "proj-b")
    ensure_project(ws.global_root, "proj-c")

    result = await delete_projects_bulk(ws, slugs=["proj-a", "proj-b"])
    assert set(result["deleted"]) == {"proj-a", "proj-b"}
    assert not result["failed"]

    snap = await library_snapshot(ws)
    slugs = {p["slug"] for p in snap["projects"]}
    assert slugs == {"proj-c"}


@pytest.mark.asyncio
async def test_bulk_delete_all_projects(tmp_path):
    ws = Workspace(tmp_path)
    ensure_project(ws.global_root, "one")
    ensure_project(ws.global_root, "two")

    result = await delete_projects_bulk(ws, delete_all=True)
    assert set(result["deleted"]) == {"one", "two"}

    snap = await library_snapshot(ws)
    assert snap["projects"] == []


@pytest.mark.asyncio
async def test_bulk_delete_invalid_slug(tmp_path):
    ws = Workspace(tmp_path)
    ensure_project(ws.global_root, "ok-proj")

    result = await delete_projects_bulk(ws, slugs=["ok-proj", ".."])
    assert result["deleted"] == ["ok-proj"]
    assert ".." in result["failed"]

    snap = await library_snapshot(ws)
    assert snap["projects"] == []
