from __future__ import annotations

import json
from pathlib import Path

from pkf.config import pkf_dir
from pkf.spec.document import SpecDocument, parse_spec


def spec_path(workspace_root: Path, name: str) -> Path:
    return pkf_dir(workspace_root) / "specs" / f"{name}.md"


def load_spec(workspace_root: Path, name: str) -> SpecDocument | None:
    path = spec_path(workspace_root, name)
    if not path.exists():
        return None
    return parse_spec(path.read_text(encoding="utf-8"))


def save_spec_document(workspace_root: Path, name: str, doc: SpecDocument) -> Path:
    path = spec_path(workspace_root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc.to_markdown(), encoding="utf-8", newline="\n")
    _sync_session(workspace_root, name, doc.status)
    return path


def approve_spec(workspace_root: Path, name: str, confirmed_stack: dict[str, str] | None = None) -> SpecDocument:
    doc = load_spec(workspace_root, name)
    if not doc:
        raise FileNotFoundError(f"Spec não encontrada: {name}")
    doc.status = "approved"
    if confirmed_stack:
        doc.confirmed_stack = {k: v for k, v in confirmed_stack.items() if v}
    save_spec_document(workspace_root, name, doc)
    return doc


def update_spec_stack(workspace_root: Path, name: str, confirmed_stack: dict[str, str]) -> SpecDocument:
    doc = load_spec(workspace_root, name)
    if not doc:
        raise FileNotFoundError(f"Spec não encontrada: {name}")
    doc.confirmed_stack = {k: v for k, v in confirmed_stack.items() if v}
    save_spec_document(workspace_root, name, doc)
    return doc


def active_spec_preview(workspace_root: Path, active_name: str | None) -> dict | None:
    if not active_name:
        return None
    doc = load_spec(workspace_root, active_name)
    if not doc:
        return None
    preview = doc.to_preview_dict()
    preview["name"] = active_name
    return preview


def _sync_session(workspace_root: Path, name: str, status: str) -> None:
    session_path = pkf_dir(workspace_root) / "session.json"
    data: dict = {}
    if session_path.exists():
        try:
            data = json.loads(session_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data["active_spec"] = name
    data["spec_status"] = status
    if status == "pending_approval":
        data["phase"] = "SPEC"
    session_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
