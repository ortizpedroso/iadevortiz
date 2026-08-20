import json
from pathlib import Path

import pytest

from pkf.projects.manager import ensure_project
from pkf.web.history import ChatHistory
from pkf.web.library import (
    activate_chat,
    attach_chat,
    create_chat,
    delete_chat,
    delete_project,
    library_snapshot,
    persist_file_messages,
    rename_project,
)
from pkf.workspace import Workspace


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


@pytest.mark.asyncio
async def test_library_create_and_list(ws: Workspace):
    snap = await library_snapshot(ws)
    assert len(snap["chats"]) >= 1
    result = await create_chat(ws)
    snap = await library_snapshot(ws)
    assert len(snap["chats"]) >= 2
    assert result["chat_id"] in {c["id"] for c in snap["chats"]}


@pytest.mark.asyncio
async def test_library_activate_chat_loads_messages(ws: Workspace):
    created = await create_chat(ws)
    chat_id = created["chat_id"]
    persist_file_messages(
        ws.global_root,
        chat_id,
        [{"role": "user", "content": "mensagem de teste"}],
    )
    messages = await activate_chat(ws, chat_id)
    assert messages[0]["content"] == "mensagem de teste"


@pytest.mark.asyncio
async def test_library_attach_and_delete_chat(ws: Workspace):
    created = await create_chat(ws)
    chat_id = created["chat_id"]
    await attach_chat(ws, chat_id, "meu-projeto", active_chat_id="other")
    assert ws.project is None
    await attach_chat(ws, chat_id, "meu-projeto", active_chat_id=chat_id)
    assert ws.project == "meu-projeto"
    snap = await library_snapshot(ws)
    chat = next(c for c in snap["chats"] if c["id"] == chat_id)
    assert chat["project_slug"] == "meu-projeto"
    await delete_chat(ws, chat_id)
    snap = await library_snapshot(ws)
    assert chat_id not in {c["id"] for c in snap["chats"]}


@pytest.mark.asyncio
async def test_library_delete_last_chat_recreates(ws: Workspace):
    snap = await library_snapshot(ws)
    for chat in list(snap["chats"]):
        await delete_chat(ws, chat["id"])
    snap = await library_snapshot(ws)
    assert len(snap["chats"]) == 1
    index = json.loads((ws.global_root / ".pkf" / "chats" / "index.json").read_text(encoding="utf-8"))
    assert index["active_id"] == snap["chats"][0]["id"]


@pytest.mark.asyncio
async def test_library_migrates_legacy_current_json(tmp_path: Path):
    legacy_dir = tmp_path / ".pkf" / "chats"
    legacy_dir.mkdir(parents=True)
    legacy = legacy_dir / "current.json"
    legacy.write_text(
        json.dumps([{"role": "user", "content": "histórico antigo"}]),
        encoding="utf-8",
    )
    ws = Workspace(tmp_path)
    snap = await library_snapshot(ws)
    assert len(snap["chats"]) == 1
    messages = await activate_chat(ws, snap["chats"][0]["id"])
    assert messages[0]["content"] == "histórico antigo"
    assert not legacy.exists()


@pytest.mark.asyncio
async def test_library_delete_project_clears_chat_slug(ws: Workspace):
    created = await create_chat(ws)
    chat_id = created["chat_id"]
    await attach_chat(ws, chat_id, "temp-proj", active_chat_id=chat_id)
    await delete_project(ws, "temp-proj")
    snap = await library_snapshot(ws)
    chat = next(c for c in snap["chats"] if c["id"] == chat_id)
    assert chat["project_slug"] is None


@pytest.mark.asyncio
async def test_library_rejects_invalid_chat_id(ws: Workspace):
    with pytest.raises(ValueError):
        await activate_chat(ws, "../etc/passwd")


@pytest.mark.asyncio
async def test_delete_active_chat_realigns_workspace(ws: Workspace):
    first = await library_snapshot(ws)
    first["chats"][0]["id"]
    created = await create_chat(ws)
    chat_b = created["chat_id"]
    await attach_chat(ws, chat_b, "proj-b", active_chat_id=chat_b)
    await delete_chat(ws, chat_b)
    assert ws.project is None or ws.project != "proj-b"


@pytest.mark.asyncio
async def test_library_rejects_path_traversal_slug(ws: Workspace):
    with pytest.raises(ValueError):
        await delete_project(ws, "..")


@pytest.mark.asyncio
async def test_library_rename_project_file_mode(ws: Workspace):
    from pkf.web.library import activate_project

    await activate_project(ws, "meu-app")
    await rename_project(ws, "meu-app", "Meu App Legal")
    snap = await library_snapshot(ws)
    project = next(p for p in snap["projects"] if p["slug"] == "meu-app")
    assert project["name"] == "Meu App Legal"
    assert ws.project_label == "Meu App Legal"


@pytest.mark.asyncio
async def test_library_rename_project_db_mode(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from pkf.db.context import DbContext
    from pkf.db.engine import close_db, init_db
    from pkf.web.library import activate_project

    ws = Workspace(tmp_path)
    ctx = DbContext(ws)
    await init_db()
    await activate_project(ws, "db-proj", ctx)
    await rename_project(ws, "db-proj", "DB Project", ctx)
    snap = await library_snapshot(ws, ctx)
    project = next(p for p in snap["projects"] if p["slug"] == "db-proj")
    assert project["name"] == "DB Project"
    await close_db()


@pytest.mark.asyncio
async def test_library_rename_rejects_empty_name(ws: Workspace):
    ensure_project(ws.global_root, "x")
    with pytest.raises(ValueError):
        await rename_project(ws, "x", "   ")


@pytest.mark.asyncio
async def test_chat_history_clear_wipes_current_chat(tmp_path: Path):
    log = ChatHistory(tmp_path)
    await log.append({"role": "user", "content": "olá"})
    await log.clear()
    again = ChatHistory(tmp_path)
    await again.load()
    assert again.messages == []
