from __future__ import annotations

import asyncio
from pathlib import Path

from pkf.config import DEFAULT_IGNORES, SECRET_NAMES, SECRET_SUFFIXES
from pkf.projects.manager import ensure_project, load_active_project, save_active_project


class WorkspaceError(ValueError):
    pass


class Workspace:
    def __init__(self, root: Path | str, project: str | None = None):
        self.global_root = Path(root).resolve()
        if not self.global_root.exists():
            self.global_root.mkdir(parents=True, exist_ok=True)
        if project is None:
            project = load_active_project(self.global_root)
        self.project = project
        if project:
            ensure_project(self.global_root, project)
            self.root = self.global_root / "projects" / project
        else:
            self.root = self.global_root
        self._file_locks: dict[str, asyncio.Lock] = {}

    def file_lock(self, rel_path: str) -> asyncio.Lock:
        key = rel_path.replace("\\", "/")
        if key not in self._file_locks:
            self._file_locks[key] = asyncio.Lock()
        return self._file_locks[key]

    def set_project(self, slug: str) -> None:
        slug = slug.strip().lower()
        ensure_project(self.global_root, slug)
        self.project = slug
        self.root = self.global_root / "projects" / slug
        save_active_project(self.global_root, slug)

    def clear_project(self) -> None:
        self.project = None
        self.root = self.global_root
        save_active_project(self.global_root, None)

    @property
    def project_label(self) -> str:
        return self.project or "(sem projeto ativo)"

    def resolve(self, rel_path: str) -> Path:
        raw = Path(rel_path)
        candidate = raw.resolve() if raw.is_absolute() else (self.root / rel_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError(f"Caminho fora do workspace: {rel_path}") from exc
        return candidate

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def is_ignored(self, path: Path) -> bool:
        try:
            parts = set(path.resolve().relative_to(self.root).parts)
        except ValueError:
            return True
        return bool(parts & DEFAULT_IGNORES)

    def is_secret(self, path: Path) -> bool:
        name = path.name.lower()
        return name in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES

    def iter_files(self, start: Path | None = None):
        base = start or self.root
        for item in base.rglob("*"):
            if not item.is_file():
                continue
            if self.is_ignored(item) or self.is_secret(item):
                continue
            yield item

    def scan_summary(self, max_entries: int = 40) -> str:
        entries: list[str] = []
        stack = self._detect_stack()
        for child in sorted(self.root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name in DEFAULT_IGNORES or child.name.startswith("."):
                continue
            kind = "dir" if child.is_dir() else "file"
            entries.append(f"- {kind}: {child.name}")
            if len(entries) >= max_entries:
                break
        lines = [
            f"Projeto: {self.project_label}",
            f"Pasta: {self.root}",
            f"Stack detectado: {', '.join(stack) if stack else 'indefinido'}",
            "Conteúdo de primeiro nível:",
            *entries,
        ]
        return "\n".join(lines)

    def _detect_stack(self) -> list[str]:
        markers = {
            "pyproject.toml": "Python",
            "requirements.txt": "Python",
            "package.json": "Node.js",
            "tsconfig.json": "TypeScript",
            "Cargo.toml": "Rust",
            "go.mod": "Go",
            "pom.xml": "Java",
            "Dockerfile": "Docker",
        }
        found: list[str] = []
        for name, label in markers.items():
            if (self.root / name).exists() and label not in found:
                found.append(label)
        if (self.root / "pkf").is_dir():
            found.append("PKF")
        return found
