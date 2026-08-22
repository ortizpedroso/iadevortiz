from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pkf.db.models import (
    ChatSession,
    FileChange,
    Message,
    Project,
    SpecRecord,
    TaskTree,
    User,
)
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


async def list_user_projects(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await session.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.updated_at.desc())
    )
    return [
        {
            "id": str(row.id),
            "slug": row.slug,
            "name": row.name or row.slug,
            "is_active": False,
        }
        for row in result.scalars()
    ]


async def list_user_chats(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await session.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
    )
    chats: list[dict] = []
    for chat in result.scalars():
        msg_result = await session.execute(
            select(Message)
            .where(Message.session_id == chat.id, Message.role == "user")
            .order_by(Message.created_at)
            .limit(1)
        )
        first = msg_result.scalar_one_or_none()
        title = "Novo chat"
        if first and first.content.strip():
            text = first.content.strip().replace("\n", " ")
            title = text[:56] + ("…" if len(text) > 56 else "")
        project_slug = None
        if chat.project_id:
            project = await session.get(Project, chat.project_id)
            project_slug = project.slug if project else None
        chats.append(
            {
                "id": str(chat.id),
                "title": title,
                "project_slug": project_slug,
                "phase": chat.phase,
                "is_active": bool(chat.is_active),
                "updated_at": chat.updated_at.isoformat() if chat.updated_at else "",
            }
        )
    return chats


async def activate_chat_session(session: AsyncSession, user: User, chat_id: uuid.UUID) -> ChatSession:
    await session.execute(
        update(ChatSession).where(ChatSession.user_id == user.id).values(is_active=False)
    )
    chat = await session.get(ChatSession, chat_id)
    if not chat or chat.user_id != user.id:
        raise ValueError("Chat não encontrado")
    chat.is_active = True
    return chat


async def attach_chat_to_project(
    session: AsyncSession,
    user: User,
    chat_id: uuid.UUID,
    project: Project | None,
) -> None:
    chat = await session.get(ChatSession, chat_id)
    if not chat or chat.user_id != user.id:
        raise ValueError("Chat não encontrado")
    chat.project_id = project.id if project else None


async def delete_chat_session(
    session: AsyncSession,
    user: User,
    chat_id: uuid.UUID,
) -> ChatSession | None:
    chat = await session.get(ChatSession, chat_id)
    if not chat or chat.user_id != user.id:
        raise ValueError("Chat não encontrado")
    was_active = chat.is_active
    await clear_messages(session, chat_id)
    trees = await session.execute(select(TaskTree).where(TaskTree.session_id == chat_id))
    for row in trees.scalars():
        await session.delete(row)
    await session.delete(chat)
    await session.flush()
    if not was_active:
        return None
    result = await session.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(1)
    )
    next_chat = result.scalar_one_or_none()
    if next_chat:
        next_chat.is_active = True
        return next_chat
    new_chat = ChatSession(user_id=user.id, is_active=True)
    session.add(new_chat)
    await session.flush()
    return new_chat


async def rename_project_record(session: AsyncSession, user: User, slug: str, name: str) -> None:
    result = await session.execute(
        select(Project).where(Project.user_id == user.id, Project.slug == slug)
    )
    project = result.scalar_one_or_none()
    if not project:
        return
    project.name = name


async def delete_project_record(
    session: AsyncSession,
    user: User,
    slug: str,
    *,
    workspace_root: Path | None = None,
) -> None:
    result = await session.execute(
        select(Project).where(Project.user_id == user.id, Project.slug == slug)
    )
    project = result.scalar_one_or_none()
    if not project:
        return
    stored_path = project.workspace_path
    await session.delete(project)
    if workspace_root is None:
        return
    candidates = []
    if stored_path:
        candidates.append(workspace_root / stored_path)
    candidates.append(workspace_root / "projects" / slug)
    for path in candidates:
        if path.is_dir():
            shutil.rmtree(path)
            break
