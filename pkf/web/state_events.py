"""Pub/Sub PostgreSQL — LISTEN pkf_state_events / NOTIFY."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import defaultdict
from typing import Any

from pkf.db.config import database_enabled, database_url

logger = logging.getLogger(__name__)

CHANNEL = "pkf_state_events"

_pending_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
_listener_task: asyncio.Task | None = None


def pending_events(session_id: str | None) -> list[dict[str, Any]]:
    if not session_id:
        return []
    return list(_pending_by_session.pop(session_id, []))


def peek_pending(session_id: str | None) -> list[dict[str, Any]]:
    if not session_id:
        return []
    return list(_pending_by_session.get(session_id, []))


def format_events_for_llm(events: list[dict[str, Any]]) -> str:
    if not events:
        return ""
    lines = ["## Atualizações de estado (sincronia autônoma)"]
    for ev in events[-5:]:
        kind = ev.get("kind", "event")
        if kind == "agent_phase_done":
            lines.append(f"- Agente `{ev.get('agent')}` concluiu tarefa `{ev.get('task_id')}`")
        else:
            lines.append(f"- {kind}: {json.dumps(ev, ensure_ascii=False)[:200]}")
    return "\n".join(lines)


async def emit_state_event(payload: dict[str, Any]) -> None:
    """Emite NOTIFY pkf_state_events (no-op se DB desabilitado)."""
    sid = payload.get("session_id")
    if sid:
        _pending_by_session[str(sid)].append(payload)
    if not database_enabled():
        return
    try:
        from sqlalchemy import text

        from pkf.db.engine import get_engine

        engine = get_engine()
        body = json.dumps(payload, ensure_ascii=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT pg_notify(:channel, :payload)"), {"channel": CHANNEL, "payload": body})
            await conn.commit()
    except (OSError, RuntimeError, ValueError, TypeError):
        logger.exception("Falha ao emitir NOTIFY %s", CHANNEL)


async def _listen_loop() -> None:
    try:
        import asyncpg
    except ImportError:
        logger.warning("asyncpg não disponível — listener %s desabilitado", CHANNEL)
        return

    url = database_url() or ""
    if not url:
        return
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    while True:
        try:
            conn = await asyncpg.connect(dsn)
            await conn.add_listener(CHANNEL, _on_notify)
            logger.info("LISTEN %s ativo", CHANNEL)
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Listener %s reconectando em 5s", CHANNEL)
            await asyncio.sleep(5)


def _on_notify(connection, pid, channel, payload) -> None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return
    sid = data.get("session_id")
    if sid:
        _pending_by_session[str(sid)].append(data)


async def start_state_listener() -> None:
    global _listener_task  # noqa: PLW0603
    if not database_enabled():
        return
    if _listener_task and not _listener_task.done():
        return
    _listener_task = asyncio.create_task(_listen_loop())


async def stop_state_listener() -> None:
    global _listener_task  # noqa: PLW0603
    if _listener_task:
        _listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _listener_task
        _listener_task = None
