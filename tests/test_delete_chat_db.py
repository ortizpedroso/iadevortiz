"""Tests for chat deletion with PostgreSQL/SQLite database mode."""

import pytest

from pkf.db.context import DbContext
from pkf.db.engine import close_db, get_session_factory, init_db
from pkf.db.repository import add_message, ensure_default_user
from pkf.web.library import create_chat, delete_chat, library_snapshot
from pkf.workspace import Workspace


@pytest.mark.asyncio
async def test_delete_chat_with_messages_db_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    ws = Workspace(tmp_path)
    ctx = DbContext(ws)
    await init_db()
    await ctx.setup()

    created = await create_chat(ws, ctx)
    chat_id = created["chat_id"]
    factory = get_session_factory()
    async with factory() as session:
        await ensure_default_user(session)
        import uuid

        await add_message(session, uuid.UUID(chat_id), "user", "mensagem de teste")
        await session.commit()

    await delete_chat(ws, chat_id, ctx)
    snap = await library_snapshot(ws, ctx)
    assert chat_id not in {c["id"] for c in snap["chats"]}
    await close_db()


@pytest.mark.asyncio
async def test_delete_inactive_chat_db_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    ws = Workspace(tmp_path)
    ctx = DbContext(ws)
    await init_db()
    await ctx.setup()

    first = await create_chat(ws, ctx)
    second = await create_chat(ws, ctx)
    await delete_chat(ws, first["chat_id"], ctx)

    snap = await library_snapshot(ws, ctx)
    ids = {c["id"] for c in snap["chats"]}
    assert first["chat_id"] not in ids
    assert second["chat_id"] in ids
    await close_db()
