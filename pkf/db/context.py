from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from pkf.db.config import database_enabled
from pkf.db.engine import get_session_factory, init_db
from pkf.db.repository import (
    add_message,
    clear_messages,
    ensure_default_user,
    get_active_session,
    get_or_create_project,
    list_file_changes_db,
    list_messages,
    load_cycle,
    load_task_tree,
    record_file_change_db,
    reset_active_session,
    save_task_tree,
    sync_cycle,
)
from pkf.workflow.cycle import DevCycle
from pkf.workspace import Workspace


class DbContext:
    """Contexto DB por request/UI — uso pessoal com user default."""

    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.user_id: uuid.UUID | None = None
        self.session_id: uuid.UUID | None = None
        self._ready = False

    @property
    def enabled(self) -> bool:
        return database_enabled()

    async def setup(self) -> None:
        if not self.enabled or self._ready:
            return
        await init_db()
        factory = get_session_factory()
        async with factory() as session:
            user = await ensure_default_user(session)
            chat = await get_active_session(session, user)
            project = await get_or_create_project(
                session, user, self.workspace.project, self.workspace.global_root
            )
            if project and chat.project_id != project.id:
                chat.project_id = project.id
            await session.commit()
            self.user_id = user.id
            self.session_id = chat.id
        self._ready = True

    @asynccontextmanager
    async def session(self):
        factory = get_session_factory()
        async with factory() as db:
            yield db
            await db.commit()

    async def get_messages(self) -> list[dict]:
        if not self.enabled or not self.session_id:
            return []
        async with self.session() as db:
            return await list_messages(db, self.session_id)

    async def append_message(self, message: dict) -> None:
        if not self.enabled or not self.session_id:
            return
        async with self.session() as db:
            await add_message(
                db,
                self.session_id,
                message.get("role", "user"),
                message.get("content", ""),
                message.get("agent"),
            )

    async def clear(self) -> None:
        if not self.enabled or not self.user_id:
            return
        async with self.session() as db:
            user = await ensure_default_user(db)
            if self.session_id:
                await clear_messages(db, self.session_id)
            chat = await reset_active_session(db, user)
            self.session_id = chat.id

    async def persist_cycle(self, cycle: DevCycle) -> None:
        if not self.enabled or not self.session_id or not self.user_id:
            return
        async with self.session() as db:
            user = await ensure_default_user(db)
            chat = await get_active_session(db, user)
            if chat.id != self.session_id:
                self.session_id = chat.id
            project = await get_or_create_project(
                db, user, self.workspace.project, self.workspace.global_root
            )
            await sync_cycle(db, chat, cycle, project)

    async def load_dev_cycle(self) -> DevCycle | None:
        if not self.enabled or not self.session_id:
            return None
        async with self.session() as db:
            from sqlalchemy import select
            from pkf.db.models import ChatSession

            result = await db.execute(select(ChatSession).where(ChatSession.id == self.session_id))
            chat = result.scalar_one_or_none()
            if not chat:
                return None
            return await load_cycle(db, chat)

    async def save_tasks(self, tree: list[dict]) -> None:
        if not self.enabled or not self.session_id:
            return
        async with self.session() as db:
            await save_task_tree(db, self.session_id, tree)

    async def load_tasks(self) -> list[dict]:
        if not self.enabled or not self.session_id:
            return []
        async with self.session() as db:
            return await load_task_tree(db, self.session_id)

    async def list_changes(self, limit: int = 20) -> list[dict]:
        if not self.enabled:
            return []
        async with self.session() as db:
            return await list_file_changes_db(db, self.session_id, limit)

    async def record_change(self, path: str, action: str, snippet: str = "") -> None:
        if not self.enabled:
            return
        async with self.session() as db:
            await record_file_change_db(db, self.session_id, path, action, snippet)
