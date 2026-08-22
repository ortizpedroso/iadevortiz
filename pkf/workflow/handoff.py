"""Persistência do delta de estado (handoff) entre agentes — substitui histórico bruto."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pkf.config import pkf_dir

HANDOFF_FILE = "session_handoffs.json"
MAX_SUMMARY = 2000  # Resumos maiores são truncados; detalhes além deste limite são perdidos.


def _handoff_path(workspace_root: Path) -> Path:
    return pkf_dir(workspace_root) / HANDOFF_FILE


def load_handoffs(workspace_root: Path) -> dict[str, Any]:
    path = _handoff_path(workspace_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_handoff(
    workspace_root: Path,
    task_id: str,
    *,
    agent: str,
    summary: str,
    artifacts: list[str] | None = None,
    status: str = "ok",
) -> dict[str, Any]:
    """Grava resumo compacto ao fim da execução de um agente."""
    store = load_handoffs(workspace_root)
    entry = {
        "agent": agent,
        "summary": (summary or "").strip()[:MAX_SUMMARY],
        "artifacts": artifacts or [],
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    store[task_id] = entry
    path = _handoff_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return store


def handoff_context_for_deps(workspace_root: Path, depends_on: list[str]) -> str:
    """Texto injetado na instrução do agente com handoffs das dependências."""
    if not depends_on:
        return ""
    store = load_handoffs(workspace_root)
    blocks: list[str] = []
    for dep_id in depends_on:
        entry = store.get(dep_id)
        if not entry:
            continue
        if entry.get("status") == "failed":
            continue
        agent = entry.get("agent", dep_id)
        summary = entry.get("summary", "")
        artifacts = entry.get("artifacts") or []
        block = f"### Handoff de `{dep_id}` ({agent})\n{summary}"
        if artifacts:
            block += "\nArtefatos verificados: " + ", ".join(artifacts[:12])
        blocks.append(block)
    if not blocks:
        return ""
    return "\n\n## Contexto de handoff (dependências concluídas)\n" + "\n\n".join(blocks)


def completed_handoff_ids(workspace_root: Path) -> list[str]:
    """task_ids com handoff ok persistido (usado na retomada de build)."""
    store = load_handoffs(workspace_root)
    return [
        task_id
        for task_id, entry in store.items()
        if isinstance(entry, dict) and entry.get("status") == "ok"
    ]


def resume_handoff_summary(workspace_root: Path, task_ids: list[str]) -> str:
    """Resumo dos handoffs disponíveis ao retomar um build interrompido."""
    if not task_ids:
        return ""
    store = load_handoffs(workspace_root)
    lines = ["Handoffs persistidos para retomada:"]
    for task_id in task_ids:
        entry = store.get(task_id)
        if not entry or entry.get("status") != "ok":
            lines.append(f"- `{task_id}`: (sem handoff ok)")
            continue
        agent = entry.get("agent", task_id)
        summary = str(entry.get("summary", ""))[:120]
        lines.append(f"- `{task_id}` ({agent}): {summary}")
    return "\n".join(lines)


def merge_db_handoffs(local: dict[str, Any], db_handoffs: dict[str, Any] | None) -> dict[str, Any]:
    if not db_handoffs:
        return local
    merged = dict(db_handoffs)
    merged.update(local)
    return merged
