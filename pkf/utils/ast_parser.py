"""Análise AST de imports Python para grafo de impacto."""

from __future__ import annotations

import ast
from pathlib import Path


def extract_imports(source: str, *, module_name: str | None = None) -> list[str]:
    """Extrai módulos importados de código Python."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
            elif node.level and module_name:
                imports.append(module_name.rsplit(".", 1)[0])
    return sorted(set(imports))


def extract_imports_from_file(path: Path) -> list[str]:
    if path.suffix.lower() != ".py" or not path.is_file():
        return []
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []
    module = path.stem if path.name != "__init__.py" else path.parent.name
    return extract_imports(source, module_name=module)
