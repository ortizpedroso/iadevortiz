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


def _project_names_path(global_root: Path) -> Path:
    return pkf_dir(global_root) / "projects" / "names.json"


def load_project_names(global_root: Path) -> dict[str, str]:
    path = _project_names_path(global_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_project_name(global_root: Path, slug: str, name: str) -> None:
    names = load_project_names(global_root)
    names[slug] = name
    path = _project_names_path(global_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_project_name(global_root: Path, slug: str) -> None:
    names = load_project_names(global_root)
    if slug in names:
        del names[slug]
        path = _project_names_path(global_root)
        if names:
            path.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
        elif path.exists():
            path.unlink()


def _pinned_path(global_root: Path) -> Path:
    return pkf_dir(global_root) / "projects" / "pinned.json"


def load_pinned_projects(global_root: Path) -> list[str]:
    path = _pinned_path(global_root)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [slug for slug in data if isinstance(slug, str)] if isinstance(data, list) else []


def set_project_pinned(global_root: Path, slug: str, pinned: bool) -> None:
    pinned_list = load_pinned_projects(global_root)
    if pinned:
        if slug not in pinned_list:
            pinned_list.append(slug)
    else:
        pinned_list = [item for item in pinned_list if item != slug]
    path = _pinned_path(global_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pinned_list, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_pinned_project(global_root: Path, slug: str) -> None:
    set_project_pinned(global_root, slug, False)


def sort_projects(projects: list[dict], global_root: Path) -> list[dict]:
    pinned_slugs = set(load_pinned_projects(global_root))
    for project in projects:
        project["pinned"] = project.get("slug") in pinned_slugs
    return sorted(
        projects,
        key=lambda project: (not project.get("pinned"), (project.get("name") or project["slug"]).lower()),
    )


def default_project_name(slug: str) -> str:
    return slug.replace("-", " ").title()


def get_project_display_name(global_root: Path, slug: str) -> str:
    return load_project_names(global_root).get(slug) or default_project_name(slug)


def load_active_project(global_root: Path) -> str | None:
    path = pkf_dir(global_root) / "project.json"
    if not path.exists():
        return _load_active_project_legacy(global_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    slug = data.get("active_project")
    return slug or None


def _load_active_project_legacy(global_root: Path) -> str | None:
    path = pkf_dir(global_root) / "session.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    slug = data.get("active_project")
    return slug or None


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
