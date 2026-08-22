"""Respostas completas de agentes durante o build — consulta barata sem reinvocar LLM."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pkf.config import BUILD_RESPONSE_MAX_CHARS, BUILD_RESPONSE_MAX_ENTRIES, pkf_dir

RESULTS_FILE = "build_agent_responses.json"


def _results_path(workspace_root: Path) -> Path:
    return pkf_dir(workspace_root) / RESULTS_FILE


def load_build_results(workspace_root: Path) -> dict[str, Any]:
    path = _results_path(workspace_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _evict_oldest(store: dict[str, Any]) -> None:
    if len(store) <= BUILD_RESPONSE_MAX_ENTRIES:
        return
    ordered = sorted(
        store.items(),
        key=lambda item: str(item[1].get("updated_at", "")),
    )
    while len(store) > BUILD_RESPONSE_MAX_ENTRIES:
        oldest_id, _ = ordered.pop(0)
        store.pop(oldest_id, None)


def save_build_result(
    workspace_root: Path,
    task_id: str,
    *,
    agent: str,
    response: str,
    status: str = "ok",
) -> None:
    """Persiste resposta integral (limitada) de uma tarefa do build."""
    store = load_build_results(workspace_root)
    text = (response or "").strip()
    if len(text) > BUILD_RESPONSE_MAX_CHARS:
        text = text[:BUILD_RESPONSE_MAX_CHARS] + "\n… [truncado]"
    store[task_id] = {
        "agent": agent,
        "response": text,
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _evict_oldest(store)
    path = _results_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def get_build_result(workspace_root: Path, task_id: str) -> dict[str, Any] | None:
    entry = load_build_results(workspace_root).get(task_id)
    return entry if isinstance(entry, dict) else None


def get_build_result_by_agent(workspace_root: Path, agent: str) -> dict[str, Any] | None:
    store = load_build_results(workspace_root)
    matches = [
        (tid, entry)
        for tid, entry in store.items()
        if isinstance(entry, dict) and entry.get("agent") == agent
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: str(item[1].get("updated_at", "")), reverse=True)
    task_id, entry = matches[0]
    return {"task_id": task_id, **entry}


def format_prior_phase_response(workspace_root: Path, task_id: str = "", agent: str = "") -> str:
    """Texto completo da resposta de uma fase anterior (não truncado como handoff)."""
    entry: dict[str, Any] | None = None
    resolved_id = task_id.strip()
    if resolved_id:
        entry = get_build_result(workspace_root, resolved_id)
        if not entry:
            return f"Nenhuma resposta registrada para task_id '{resolved_id}'."
    elif agent.strip():
        found = get_build_result_by_agent(workspace_root, agent.strip())
        if not found:
            return f"Nenhuma resposta registrada para agente '{agent}'."
        resolved_id = str(found.get("task_id", ""))
        entry = found
    else:
        return "Informe task_id ou agent."

    assert entry is not None
    response = str(entry.get("response") or "").strip() or "(sem texto)"
    status = entry.get("status", "ok")
    agent_name = entry.get("agent", "?")
    lines = [
        f"# Resposta completa — `{resolved_id}` ({agent_name})",
        f"Status: {status}",
        "",
        response,
    ]
    return "\n".join(lines)
