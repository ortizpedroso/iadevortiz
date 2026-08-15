from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from pkf.workspace import Workspace

PREVIEW_ROOT = ".pkf"
ENTRY_CANDIDATES = (
    "index.html",
    "index.htm",
    "public/index.html",
    "dist/index.html",
)


def _blocked_preview_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/").lstrip("/")
    return normalized == PREVIEW_ROOT or normalized.startswith(f"{PREVIEW_ROOT}/")


def find_preview_entry(workspace: Workspace) -> str | None:
    for rel in ENTRY_CANDIDATES:
        target = workspace.root / rel
        if target.is_file() and not workspace.is_secret(target) and not _blocked_preview_path(rel):
            return rel.replace("\\", "/")
    return None


def list_preview_files(workspace: Workspace, limit: int = 30) -> list[str]:
    files: list[str] = []
    for item in workspace.iter_files():
        rel = workspace.rel(item)
        if _blocked_preview_path(rel):
            continue
        files.append(rel)
        if len(files) >= limit:
            break
    return sorted(files)


def preview_info(workspace: Workspace) -> dict:
    entry = find_preview_entry(workspace)
    files = list_preview_files(workspace)
    return {
        "available": entry is not None,
        "entry": entry,
        "files": files,
    }


def preview_path(workspace: Workspace, rel_path: str = "") -> Path:
    cleaned = rel_path.strip().lstrip("/")
    if not cleaned:
        entry = find_preview_entry(workspace)
        if not entry:
            raise HTTPException(status_code=404, detail="Nenhuma página de preview encontrada. Rode /build primeiro.")
        cleaned = entry
    if _blocked_preview_path(cleaned):
        raise HTTPException(status_code=403, detail="Arquivo não disponível para preview.")
    try:
        target = workspace.resolve(cleaned)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if workspace.is_secret(target):
        raise HTTPException(status_code=403, detail="Arquivo protegido.")
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {cleaned}")
    return target


def serve_preview_file(workspace: Workspace, rel_path: str = ""):
    target = preview_path(workspace, rel_path)
    media_type, _ = mimetypes.guess_type(target.name)
    return FileResponse(target, media_type=media_type or "application/octet-stream")


def redirect_preview_entry(workspace: Workspace, token: str | None):
    entry = find_preview_entry(workspace)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma página encontrada. Use /build para gerar index.html no workspace.",
        )
    suffix = f"?token={token}" if token else ""
    return RedirectResponse(url=f"/preview/{entry}{suffix}")
