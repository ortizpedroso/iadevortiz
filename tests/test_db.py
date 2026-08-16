import pytest

from pkf.db.context import DbContext
from pkf.db.engine import close_db, init_db
from pkf.workspace import Workspace


@pytest.mark.asyncio
async def test_db_messages_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    ws = Workspace(tmp_path)
    ctx = DbContext(ws)
    await init_db()
    await ctx.setup()
    await ctx.append_message({"role": "user", "content": "teste db"})
    msgs = await ctx.get_messages()
    assert msgs[-1]["content"] == "teste db"
    await close_db()
