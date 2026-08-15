from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from pkf.config import pkf_dir

PROJECTS_DIR = "projects"


def slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", ascii_text.strip().lower()).strip("-")
    return cleaned or "projeto"


def project_dir(global_root: Path, slug: str) -> Path:
    return global_root / PROJECTS_DIR / slug


def ensure_project(global_root: Path, slug: str) -> Path:
    path = project_dir(global_root, slug)
    path.mkdir(parents=True, exist_ok=True)
    pkf_dir(path).mkdir(parents=True, exist_ok=True)
    return path


def list_projects(global_root: Path) -> list[str]:
    base = global_root / PROJECTS_DIR
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


def load_active_project(global_root: Path) -> str | None:
    path = pkf_dir(global_root) / "project.json"
    if not path.exists():
        return _load_active_project_legacy(global_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    slug = data.get("active_project")
    return slug if slug else None


def _load_active_project_legacy(global_root: Path) -> str | None:
    path = pkf_dir(global_root) / "session.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    slug = data.get("active_project")
    return slug if slug else None


def save_active_project(global_root: Path, slug: str | None) -> None:
    path = pkf_dir(global_root) / "project.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if slug:
        path.write_text(json.dumps({"active_project": slug}, ensure_ascii=False, indent=2), encoding="utf-8")
    elif path.exists():
        path.unlink()


def slug_from_request(text: str) -> str:
    first_line = text.strip().splitlines()[0][:80]
    return slugify(first_line.replace(" ", "-"))
