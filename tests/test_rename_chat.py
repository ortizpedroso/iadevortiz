"""Testes de renomear chat via library."""

from __future__ import annotations

import pytest

from pkf.web.library import library_snapshot, rename_chat
from pkf.workspace import Workspace


@pytest.mark.asyncio
async def test_rename_chat_updates_title_in_file_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    ws = Workspace(tmp_path)
    from pkf.web.library import create_chat

    result = await create_chat(ws, None)
    chat_id = result["chat_id"]
    await rename_chat(ws, chat_id, "Meu chat renomeado", None)
    snapshot = await library_snapshot(ws, None)
    chat = next(c for c in snapshot["chats"] if c["id"] == chat_id)
    assert chat["title"] == "Meu chat renomeado"
