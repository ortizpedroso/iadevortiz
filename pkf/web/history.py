from __future__ import annotations

import json
from pathlib import Path

from pkf.config import pkf_dir
from pkf.db.config import database_enabled
from pkf.db.context import DbContext
from pkf.workspace import Workspace


class ChatHistory:
    def __init__(self, workspace_root: Path, workspace: Workspace | None = None):
        ws = workspace or Workspace(workspace_root)
        self.workspace = ws
        self.path = pkf_dir(workspace_root) / "chats" / "current.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = DbContext(ws)
        self.messages: list[dict] = []

    async def load(self) -> None:
        if database_enabled():
            await self.db.setup()
            self.messages = await self.db.get_messages()
            return
        self.messages = self._load_file()

    def _load_file(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    async def _save_file(self) -> None:
        self.path.write_text(json.dumps(self.messages, ensure_ascii=False, indent=2), encoding="utf-8")

    async def append(self, message: dict) -> None:
        self.messages.append(message)
        if database_enabled():
            await self.db.setup()
            await self.db.append_message(message)
        else:
            await self._save_file()

    async def clear(self) -> None:
        self.messages = []
        if database_enabled():
            await self.db.clear()
        elif self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    @property
    def db_context(self) -> DbContext:
        return self.db
