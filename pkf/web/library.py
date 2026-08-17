from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pkf.config import pkf_dir
from pkf.db.config import database_enabled
from pkf.db.context import DbContext
from pkf.db.engine import get_session_factory, init_db
from pkf.db.repository import (
    activate_chat_session,
    attach_chat_to_project,
    delete_chat_session,
    delete_project_record,
    ensure_default_user,
    get_or_create_project,
    list_user_chats,
    list_user_projects,
)
from pkf.projects.manager import ensure_project, list_projects, project_dir, save_active_project
from pkf.workspace import Workspace


def _chats_dir(workspace_root: Path) -> Path:
    path = pkf_dir(workspace_root) / "chats"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_path(workspace_root: Path) -> Path:
    return _chats_dir(workspace_root) / "index.json"


def _load_index(workspace_root: Path) -> dict:
    path = _index_path(workspace_root)
    if not path.exists():
        return {"active_id": None, "chats": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"active_id": None, "chats": []}
    if not isinstance(data.get("chats"), list):
        data["chats"] = []
    return data


def _save_index(workspace_root: Path, data: dict) -> None:
    _index_path(workspace_root).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _validate_chat_id(chat_id: str) -> str:
    chat_id = chat_id.strip()
    if re.fullmatch(r"[a-f0-9]{12}", chat_id):
        return chat_id
    try:
        return str(uuid.UUID(chat_id))
    except ValueError as exc:
        raise ValueError("Chat inválido") from exc


def _chat_file(workspace_root: Path, chat_id: str) -> Path:
    safe_id = _validate_chat_id(chat_id)
    if not re.fullmatch(r"[a-f0-9]{12}", safe_id):
        raise ValueError("Chat inválido")
    return _chats_dir(workspace_root) / f"{safe_id}.json"


def _apply_active_chat_project(workspace: Workspace, data: dict) -> None:
    active_id = data.get("active_id")
    if not active_id:
        workspace.clear_project()
        return
    chat = next((c for c in data.get("chats", []) if c.get("id") == active_id), None)
    if chat and chat.get("project_slug"):
        workspace.set_project(chat["project_slug"])
    else:
        workspace.clear_project()


def _validate_slug(slug: str) -> str:
    slug = slug.strip()
    if not slug or ".." in slug or "/" in slug or "\\" in slug:
        raise ValueError("Projeto inválido")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", slug):
        raise ValueError("Projeto inválido")
    return slug


def _safe_project_path(global_root: Path, slug: str) -> Path:
    slug = _validate_slug(slug)
    base = (global_root / "projects").resolve()
    path = project_dir(global_root, slug).resolve()
    if base not in path.parents and path != base:
        raise ValueError("Projeto inválido")
    return path


def _migrate_legacy_chat(workspace_root: Path) -> None:
    if _index_path(workspace_root).exists():
        return
    legacy = pkf_dir(workspace_root) / "chats" / "current.json"
    if not legacy.exists():
        return
    try:
        messages = json.loads(legacy.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        messages = []
    if not isinstance(messages, list):
        messages = []
    chat_id = uuid.uuid4().hex[:12]
    title = "Novo chat"
    for msg in messages:
        if msg.get("role") == "user" and (msg.get("content") or "").strip():
            text = msg["content"].strip().replace("\n", " ")
            title = text[:56] + ("…" if len(text) > 56 else "")
            break
    data = {
        "active_id": chat_id,
        "chats": [
            {
                "id": chat_id,
                "title": title,
                "project_slug": None,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ],
    }
    _chat_file(workspace_root, chat_id).write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _save_index(workspace_root, data)
    backup = legacy.with_suffix(".json.bak")
    try:
        legacy.rename(backup)
    except OSError:
        pass


def _ensure_file_chat(workspace_root: Path) -> dict:
    _migrate_legacy_chat(workspace_root)
    data = _load_index(workspace_root)
    if not data["chats"]:
        chat_id = uuid.uuid4().hex[:12]
        data["active_id"] = chat_id
        data["chats"] = [
            {
                "id": chat_id,
                "title": "Novo chat",
                "project_slug": None,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ]
        _chat_file(workspace_root, chat_id).write_text("[]", encoding="utf-8")
        _save_index(workspace_root, data)
    elif not data.get("active_id"):
        data["active_id"] = data["chats"][0]["id"]
        _save_index(workspace_root, data)
    return data


def _file_list_chats(workspace_root: Path) -> list[dict]:
    data = _ensure_file_chat(workspace_root)
    active = data.get("active_id")
    return [
        {
            **chat,
            "is_active": chat.get("id") == active,
        }
        for chat in data.get("chats", [])
    ]


def _file_list_projects(global_root: Path, active_slug: str | None) -> list[dict]:
    return [
        {
            "slug": slug,
            "name": slug.replace("-", " ").title(),
            "is_active": slug == active_slug,
        }
        for slug in list_projects(global_root)
    ]


async def library_snapshot(workspace: Workspace, db: DbContext | None = None) -> dict:
    if database_enabled() and db:
        await db.setup()
        factory = get_session_factory()
        async with factory() as session:
            user = await ensure_default_user(session)
            chats = await list_user_chats(session, user.id)
            projects = await list_user_projects(session, user.id)
            await session.commit()
        active_slug = workspace.project
        for project in projects:
            project["is_active"] = project.get("slug") == active_slug
        known = {p["slug"] for p in projects}
        for slug in list_projects(workspace.global_root):
            if slug not in known:
                projects.append(
                    {
                        "slug": slug,
                        "name": slug.replace("-", " ").title(),
                        "is_active": slug == active_slug,
                    }
                )
        projects.sort(key=lambda p: (p.get("name") or p["slug"]).lower())
        return {"chats": chats, "projects": projects, "active_chat_id": str(db.session_id) if db.session_id else None}

    global_root = workspace.global_root
    data = _ensure_file_chat(global_root)
    return {
        "chats": _file_list_chats(global_root),
        "projects": _file_list_projects(global_root, workspace.project),
        "active_chat_id": data.get("active_id"),
    }


async def create_chat(workspace: Workspace, db: DbContext | None = None) -> dict:
    if database_enabled() and db:
        from pkf.db.repository import reset_active_session

        await db.setup()
        factory = get_session_factory()
        async with factory() as session:
            user = await ensure_default_user(session)
            chat = await reset_active_session(session, user)
            if workspace.project:
                project = await get_or_create_project(
                    session, user, workspace.project, workspace.global_root
                )
                chat.project_id = project.id
            await session.commit()
            db.session_id = chat.id
        return {"ok": True, "chat_id": str(chat.id)}

    global_root = workspace.global_root
    data = _load_index(global_root)
    chat_id = uuid.uuid4().hex[:12]
    data["chats"].insert(
        0,
        {
            "id": chat_id,
            "title": "Novo chat",
            "project_slug": workspace.project,
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    data["active_id"] = chat_id
    _chat_file(global_root, chat_id).write_text("[]", encoding="utf-8")
    _save_index(global_root, data)
    return {"ok": True, "chat_id": chat_id}


async def activate_chat(workspace: Workspace, chat_id: str, db: DbContext | None = None) -> list[dict]:
    chat_id = _validate_chat_id(chat_id)
    if database_enabled() and db:
        from pkf.db.models import Project
        from pkf.db.repository import list_messages

        await db.setup()
        factory = get_session_factory()
        async with factory() as session:
            user = await ensure_default_user(session)
            chat = await activate_chat_session(session, user, uuid.UUID(chat_id))
            if chat.project_id:
                project = await session.get(Project, chat.project_id)
                if project and project.slug:
                    workspace.set_project(project.slug)
            else:
                workspace.clear_project()
            await session.commit()
            db.session_id = chat.id
            return await list_messages(session, uuid.UUID(chat_id))

    global_root = workspace.global_root
    data = _load_index(global_root)
    if not any(c.get("id") == chat_id for c in data.get("chats", [])):
        raise ValueError("Chat não encontrado")
    data["active_id"] = chat_id
    _save_index(global_root, data)
    path = _chat_file(global_root, chat_id)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")
    try:
        messages = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        messages = []
    chat = next(c for c in data["chats"] if c["id"] == chat_id)
    if chat.get("project_slug"):
        workspace.set_project(chat["project_slug"])
    else:
        workspace.clear_project()
    return messages if isinstance(messages, list) else []


async def delete_chat(workspace: Workspace, chat_id: str, db: DbContext | None = None) -> None:
    chat_id = _validate_chat_id(chat_id)
    if database_enabled() and db:
        from pkf.db.models import Project

        await db.setup()
        factory = get_session_factory()
        async with factory() as session:
            user = await ensure_default_user(session)
            current_id = db.session_id
            deleted_id = uuid.UUID(chat_id)
            new_active = await delete_chat_session(session, user, deleted_id)
            if current_id == deleted_id:
                if new_active and new_active.project_id:
                    project = await session.get(Project, new_active.project_id)
                    if project and project.slug:
                        workspace.set_project(project.slug)
                    else:
                        workspace.clear_project()
                else:
                    workspace.clear_project()
                db.session_id = new_active.id if new_active else None
            await session.commit()
        return

    global_root = workspace.global_root
    data = _load_index(global_root)
    data["chats"] = [c for c in data.get("chats", []) if c.get("id") != chat_id]
    path = _chat_file(global_root, chat_id)
    if path.exists():
        path.unlink()
    if data.get("active_id") == chat_id:
        data["active_id"] = data["chats"][0]["id"] if data["chats"] else None
    if not data["chats"]:
        chat_id = uuid.uuid4().hex[:12]
        data["chats"] = [
            {
                "id": chat_id,
                "title": "Novo chat",
                "project_slug": None,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ]
        data["active_id"] = chat_id
        _chat_file(global_root, chat_id).write_text("[]", encoding="utf-8")
    _save_index(global_root, data)
    _apply_active_chat_project(workspace, data)


async def attach_chat(
    workspace: Workspace,
    chat_id: str,
    project_slug: str | None,
    db: DbContext | None = None,
    active_chat_id: str | None = None,
) -> None:
    chat_id = _validate_chat_id(chat_id)
    slug = (project_slug or "").strip() or None
    if slug:
        slug = _validate_slug(slug)
    if database_enabled() and db:
        await db.setup()
        factory = get_session_factory()
        async with factory() as session:
            user = await ensure_default_user(session)
            project = await get_or_create_project(session, user, slug, workspace.global_root) if slug else None
            await attach_chat_to_project(session, user, uuid.UUID(chat_id), project)
            await session.commit()
        is_active = active_chat_id == chat_id or (db.session_id and str(db.session_id) == chat_id)
        if is_active:
            if slug:
                workspace.set_project(slug)
            else:
                workspace.clear_project()
        return

    global_root = workspace.global_root
    data = _load_index(global_root)
    for chat in data.get("chats", []):
        if chat.get("id") == chat_id:
            chat["project_slug"] = slug
            chat["updated_at"] = datetime.now(UTC).isoformat()
    _save_index(global_root, data)
    if active_chat_id == chat_id:
        if slug:
            ensure_project(global_root, slug)
            workspace.set_project(slug)
        else:
            workspace.clear_project()


async def delete_project(workspace: Workspace, slug: str, db: DbContext | None = None) -> None:
    slug = _validate_slug(slug)
    if database_enabled() and db:
        await db.setup()
        factory = get_session_factory()
        async with factory() as session:
            user = await ensure_default_user(session)
            await delete_project_record(session, user, slug)
            await session.commit()

    global_root = workspace.global_root
    data = _load_index(global_root)
    for chat in data.get("chats", []):
        if chat.get("project_slug") == slug:
            chat["project_slug"] = None
            chat["updated_at"] = datetime.now(UTC).isoformat()
    _save_index(global_root, data)

    project_path = _safe_project_path(global_root, slug)
    if project_path.is_dir():
        shutil.rmtree(project_path)
    if workspace.project == slug:
        workspace.clear_project()
        save_active_project(global_root, None)


async def activate_project(workspace: Workspace, slug: str, db: DbContext | None = None) -> None:
    slug = _validate_slug(slug) if slug.strip() else ""
    if not slug:
        workspace.clear_project()
        save_active_project(workspace.global_root, None)
        return
    ensure_project(workspace.global_root, slug)
    workspace.set_project(slug)
    save_active_project(workspace.global_root, slug)
    if database_enabled() and db:
        await db.setup()
        factory = get_session_factory()
        async with factory() as session:
            user = await ensure_default_user(session)
            project = await get_or_create_project(session, user, slug, workspace.global_root)
            if db.session_id and project:
                from pkf.db.models import ChatSession

                chat = await session.get(ChatSession, db.session_id)
                if chat:
                    chat.project_id = project.id
            await session.commit()


def sync_file_chat_meta(workspace_root: Path, chat_id: str | None, messages: list[dict]) -> None:
    if not chat_id:
        return
    data = _load_index(workspace_root)
    title = "Novo chat"
    for msg in messages:
        if msg.get("role") == "user" and (msg.get("content") or "").strip():
            text = msg["content"].strip().replace("\n", " ")
            title = text[:56] + ("…" if len(text) > 56 else "")
            break
    for chat in data.get("chats", []):
        if chat.get("id") == chat_id:
            chat["title"] = title
            chat["updated_at"] = datetime.now(UTC).isoformat()
            break
    _save_index(workspace_root, data)


def persist_file_messages(workspace_root: Path, chat_id: str | None, messages: list[dict]) -> None:
    if not chat_id:
        return
    _chat_file(workspace_root, chat_id).write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sync_file_chat_meta(workspace_root, chat_id, messages)


def load_file_messages(workspace_root: Path) -> tuple[str | None, list[dict]]:
    data = _ensure_file_chat(workspace_root)
    chat_id = data.get("active_id")
    if not chat_id:
        return None, []
    path = _chat_file(workspace_root, chat_id)
    if not path.exists():
        return chat_id, []
    try:
        messages = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        messages = []
    return chat_id, messages if isinstance(messages, list) else []
