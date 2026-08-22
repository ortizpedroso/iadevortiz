"""Grafo de impacto entre arquivos (BFS a partir de mudanças)."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from pkf.config import pkf_dir
from pkf.utils.ast_parser import extract_imports_from_file

GRAPH_FILE = "impact_graph.json"


def _graph_path(workspace_root: Path) -> Path:
    return pkf_dir(workspace_root) / GRAPH_FILE


def load_impact_graph(workspace_root: Path) -> dict:
    path = _graph_path(workspace_root)
    if not path.exists():
        return {"files": {}, "edges": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"files": {}, "edges": {}}
    return data


def save_impact_graph(workspace_root: Path, graph: dict) -> None:
    path = _graph_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")


def register_file(workspace_root: Path, rel_path: str, absolute: Path) -> None:
    """Atualiza nó do arquivo e arestas import → arquivo."""
    graph = load_impact_graph(workspace_root)
    files = graph.setdefault("files", {})
    edges = graph.setdefault("edges", {})
    imports = extract_imports_from_file(absolute)
    files[rel_path] = {"imports": imports}
    for mod in imports:
        edges.setdefault(mod, [])
        if rel_path not in edges[mod]:
            edges[mod].append(rel_path)
    save_impact_graph(workspace_root, graph)


def bfs_affected_files(workspace_root: Path, changed_path: str) -> list[str]:
    """Arquivos impactados via BFS no grafo de imports."""
    graph = load_impact_graph(workspace_root)
    files = graph.get("files") or {}
    if changed_path not in files:
        return [changed_path]
    visited: set[str] = set()
    queue: deque[str] = deque([changed_path])
    affected: list[str] = []
    changed_mod = Path(changed_path).stem
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        affected.append(current)
        meta = files.get(current) or {}
        for imp in meta.get("imports") or []:
            for path, _info in files.items():
                if path in visited:
                    continue
                stem = Path(path).stem
                if stem == imp or path.endswith((f"/{imp}.py", f"{imp}/__init__.py")):
                    queue.append(path)
        for path, info in files.items():
            if path in visited:
                continue
            if changed_mod in (info.get("imports") or []):
                queue.append(path)
    return affected


def store_review_scope(workspace_root: Path, paths: list[str]) -> None:
    scope_path = pkf_dir(workspace_root) / "review_scope.json"
    scope_path.write_text(json.dumps({"paths": paths}, ensure_ascii=False, indent=2), encoding="utf-8")


def load_review_scope(workspace_root: Path) -> list[str]:
    scope_path = pkf_dir(workspace_root) / "review_scope.json"
    if not scope_path.exists():
        return []
    try:
        data = json.loads(scope_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    paths = data.get("paths") if isinstance(data, dict) else []
    return [str(p) for p in paths] if isinstance(paths, list) else []
