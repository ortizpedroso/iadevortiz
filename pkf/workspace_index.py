from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from pkf.config import pkf_dir
from pkf.workspace import Workspace

_locks: dict[str, threading.RLock] = {}


def _lock_for(root: Path) -> threading.RLock:
    key = str(root.resolve())
    if key not in _locks:
        _locks[key] = threading.RLock()
    return _locks[key]


def begin_build_session(workspace: Workspace) -> None:
    session_path = pkf_dir(workspace.root) / "build_session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({"started_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )


def record_change(workspace: Workspace, path: str, action: str, snippet: str = "") -> None:
    log_path = pkf_dir(workspace.root) / "changes.json"
    with _lock_for(workspace.root):
        entries: list[dict] = []
        if log_path.exists():
            try:
                entries = json.loads(log_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                entries = []
        entries.append(
            {
                "path": path.replace("\\", "/"),
                "action": action,
                "snippet": snippet[:500],
                "at": datetime.now(UTC).isoformat(),
            }
        )
        log_path.write_text(json.dumps(entries[-50:], ensure_ascii=False, indent=2), encoding="utf-8")


def list_changes(workspace: Workspace, limit: int = 20) -> list[dict]:
    log_path = pkf_dir(workspace.root) / "changes.json"
    if not log_path.exists():
        return []
    try:
        entries = json.loads(log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return entries[-limit:]


def build_file_tree(workspace: Workspace, max_depth: int = 4) -> list[dict]:
    root = workspace.root

    def walk(path: Path, depth: int) -> list[dict]:
        if depth > max_depth:
            return []
        items: list[dict] = []
        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return []
        for child in children:
            if workspace.is_ignored(child) or workspace.is_secret(child):
                continue
            rel = workspace.rel(child)
            if child.is_dir():
                items.append({"path": rel, "type": "dir", "children": walk(child, depth + 1)})
            else:
                items.append({"path": rel, "type": "file"})
        return items

    return walk(root, 0)


def verify_workspace_files(workspace: Workspace) -> dict:
    session_path = pkf_dir(workspace.root) / "build_session.json"
    if not session_path.exists():
        return {"ok": False, "count": 0, "files": [], "reason": "no_build_session"}
    try:
        started_at = json.loads(session_path.read_text(encoding="utf-8"))["started_at"]
    except (json.JSONDecodeError, KeyError):
        return {"ok": False, "count": 0, "files": [], "reason": "invalid_session"}
    recent = [c for c in list_changes(workspace, limit=50) if c.get("at", "") >= started_at]
    files = list(dict.fromkeys(c["path"] for c in recent))
    return {"ok": len(files) > 0, "count": len(files), "files": files}


def build_code_index(workspace: Workspace) -> str:
    index_path = pkf_dir(workspace.root) / "index" / "code.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for file_path in workspace.iter_files():
        rel = workspace.rel(file_path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        first_lines = "\n".join(text.splitlines()[:8])
        entries.append({"path": rel, "preview": first_lines[:400]})
        if len(entries) >= 200:
            break
    index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"Índice atualizado: {len(entries)} arquivos em {index_path.name}"


def query_code_index(workspace: Workspace, query: str) -> str:
    index_path = pkf_dir(workspace.root) / "index" / "code.json"
    if not index_path.exists():
        build_code_index(workspace)
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "Índice indisponível."
    q = query.lower()
    hits = [e for e in entries if q in e.get("path", "").lower() or q in e.get("preview", "").lower()]
    if not hits:
        return "Nenhum resultado no índice."
    return "\n\n".join(f"{h['path']}:\n{h['preview'][:200]}" for h in hits[:15])
