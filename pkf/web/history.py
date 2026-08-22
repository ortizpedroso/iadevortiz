from __future__ import annotations

import json
from pathlib import Path

from pkf.config import pkf_dir
from pkf.db.config import database_enabled
from pkf.db.context import DbContext
from pkf.web.library import load_file_messages, persist_file_messages
from pkf.workspace import Workspace


class ChatHistory:
    def __init__(self, workspace_root: Path, workspace: Workspace | None = None):
        ws = workspace or Workspace(workspace_root)
        self.workspace = ws
        self.path = pkf_dir(workspace_root) / "chats" / "current.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = DbContext(ws)
        self.messages: list[dict] = []
        self.active_chat_id: str | None = None

    async def load(self) -> None:
        if database_enabled():
            try:
                await self.db.setup()
                self.messages = await self.db.get_messages()
                self.active_chat_id = str(self.db.session_id) if self.db.session_id else None
                return
            except Exception:
                import logging

                logging.getLogger(__name__).exception(
                    "Falha ao carregar histórico do Postgres; usando fallback em arquivo"
                )
        self.active_chat_id, self.messages = load_file_messages(self.workspace.global_root)

    def _load_legacy_file(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    async def _save_file(self) -> None:
        persist_file_messages(self.workspace.global_root, self.active_chat_id, self.messages)

    async def append(self, message: dict) -> None:
        if not database_enabled() and not self.active_chat_id:
            await self.load()
        self.messages.append(message)
        if database_enabled():
            await self.db.setup()
            await self.db.append_message(message)
        else:
            await self._save_file()

    async def replace_messages(self, messages: list[dict]) -> None:
        # Pendência (L3): diff/bulk insert em vez de apagar+reinserir tudo.
        self.messages = list(messages)
        if database_enabled():
            await self.db.setup()
            if self.db.session_id:
                from pkf.db.engine import get_session_factory
                from pkf.db.repository import clear_messages

                factory = get_session_factory()
                async with factory() as session:
                    await clear_messages(session, self.db.session_id)
                    for msg in messages:
                        from pkf.db.repository import add_message

                        await add_message(
                            session,
                            self.db.session_id,
                            msg.get("role", "user"),
                            msg.get("content", ""),
                            msg.get("agent"),
                        )
                    await session.commit()
        else:
            await self._save_file()

    async def clear(self) -> None:
        self.messages = []
        if database_enabled():
            await self.db.clear()
            self.active_chat_id = str(self.db.session_id) if self.db.session_id else None
        else:
            if not self.active_chat_id:
                await self.load()
            await self._save_file()

    @property
    def db_context(self) -> DbContext:
        return self.db
