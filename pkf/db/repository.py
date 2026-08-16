from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pkf.db.models import ChatSession, FileChange, Message, Project, SpecRecord, TaskTree, User
from pkf.workflow.cycle import DevCycle


DEFAULT_USER_EMAIL = "owner@pkf.local"


async def ensure_default_user(session: AsyncSession) -> User:
    result = await session.execute(select(User).where(User.email == DEFAULT_USER_EMAIL))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(email=DEFAULT_USER_EMAIL, display_name="Owner")
    session.add(user)
    await session.flush()
    return user


async def get_or_create_project(
    session: AsyncSession,
    user: User,
    slug: str | None,
    workspace_root: Path,
) -> Project | None:
    if not slug:
        return None
    result = await session.execute(
        select(Project).where(Project.user_id == user.id, Project.slug == slug)
    )
    project = result.scalar_one_or_none()
    rel_path = f"projects/{slug}"
    if project:
        project.workspace_path = rel_path
        return project
    project = Project(user_id=user.id, slug=slug, name=slug, workspace_path=rel_path)
    session.add(project)
    await session.flush()
    return project


async def get_active_session(session: AsyncSession, user: User) -> ChatSession:
    result = await session.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id, ChatSession.is_active.is_(True))
        .order_by(ChatSession.updated_at.desc())
        .limit(1)
    )
    chat = result.scalar_one_or_none()
    if chat:
        return chat
    chat = ChatSession(user_id=user.id)
    session.add(chat)
    await session.flush()
    return chat


async def reset_active_session(session: AsyncSession, user: User) -> ChatSession:
    await session.execute(
        update(ChatSession).where(ChatSession.user_id == user.id).values(is_active=False)
    )
    chat = ChatSession(user_id=user.id)
    session.add(chat)
    await session.flush()
    return chat


async def list_messages(session: AsyncSession, chat_session_id: uuid.UUID) -> list[dict]:
    result = await session.execute(
        select(Message)
        .where(Message.session_id == chat_session_id)
        .order_by(Message.created_at)
    )
    rows = result.scalars().all()
    out: list[dict] = []
    for row in rows:
        item = {"role": row.role, "content": row.content}
        if row.agent:
            item["agent"] = row.agent
        out.append(item)
    return out


async def add_message(
    session: AsyncSession,
    chat_session_id: uuid.UUID,
    role: str,
    content: str,
    agent: str | None = None,
) -> None:
    session.add(
        Message(session_id=chat_session_id, role=role, content=content, agent=agent)
    )


async def clear_messages(session: AsyncSession, chat_session_id: uuid.UUID) -> None:
    result = await session.execute(select(Message).where(Message.session_id == chat_session_id))
    for row in result.scalars():
        await session.delete(row)


async def sync_cycle(session: AsyncSession, chat: ChatSession, cycle: DevCycle, project: Project | None) -> None:
    chat.phase = cycle.phase
    chat.active_spec = cycle.active_spec
    chat.spec_status = cycle.spec_status
    chat.goal = cycle.goal
    chat.last_agent = cycle.last_agent
    chat.project_id = project.id if project else None


async def load_cycle(session: AsyncSession, chat: ChatSession) -> DevCycle:
    return DevCycle(
        phase=chat.phase or "IDLE",
        active_spec=chat.active_spec,
        spec_status=chat.spec_status,
        last_agent=chat.last_agent,
        goal=chat.goal,
    )


async def save_task_tree(session: AsyncSession, chat_session_id: uuid.UUID, tree: list[dict]) -> None:
    result = await session.execute(
        select(TaskTree).where(TaskTree.session_id == chat_session_id).order_by(TaskTree.updated_at.desc())
    )
    row = result.scalars().first()
    if row:
        row.tree = tree
    else:
        session.add(TaskTree(session_id=chat_session_id, tree=tree))


async def load_task_tree(session: AsyncSession, chat_session_id: uuid.UUID) -> list[dict]:
    result = await session.execute(
        select(TaskTree).where(TaskTree.session_id == chat_session_id).order_by(TaskTree.updated_at.desc())
    )
    row = result.scalars().first()
    return row.tree if row else []


async def record_file_change_db(
    session: AsyncSession,
    chat_session_id: uuid.UUID | None,
    path: str,
    action: str,
    snippet: str = "",
) -> None:
    session.add(
        FileChange(session_id=chat_session_id, path=path, action=action, snippet=snippet[:500])
    )


async def list_file_changes_db(session: AsyncSession, chat_session_id: uuid.UUID | None, limit: int = 20) -> list[dict]:
    q = select(FileChange).order_by(FileChange.created_at.desc()).limit(limit)
    if chat_session_id:
        q = q.where(FileChange.session_id == chat_session_id)
    result = await session.execute(q)
    return [
        {"path": row.path, "action": row.action, "snippet": row.snippet, "at": row.created_at.isoformat()}
        for row in result.scalars()
    ]


async def upsert_spec_record(
    session: AsyncSession,
    project: Project | None,
    slug: str,
    title: str,
    body: str,
    status: str,
    suggested_stack: dict,
    confirmed_stack: dict,
) -> None:
    q = select(SpecRecord).where(SpecRecord.slug == slug)
    if project:
        q = q.where(SpecRecord.project_id == project.id)
    result = await session.execute(q)
    row = result.scalar_one_or_none()
    if row:
        row.title = title
        row.body = body
        row.status = status
        row.suggested_stack = suggested_stack
        row.confirmed_stack = confirmed_stack
    else:
        session.add(
            SpecRecord(
                project_id=project.id if project else None,
                slug=slug,
                title=title,
                body=body,
                status=status,
                suggested_stack=suggested_stack,
                confirmed_stack=confirmed_stack,
            )
        )
