from __future__ import annotations

from datetime import UTC, datetime

from pkf.config import pkf_dir
from pkf.spec.document import SpecDocument
from pkf.spec.store import load_spec, save_spec_document
from pkf.workspace_index import list_changes


def append_build_changelog(workspace_root, spec_name: str | None) -> None:
    if not spec_name:
        return
    doc = load_spec(workspace_root, spec_name)
    if not doc:
        return
    changes = list_changes_for_spec(workspace_root)
    if not changes:
        return
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"\n\n## Changelog ({stamp})\n"]
    for item in changes:
        lines.append(f"- `{item['path']}` ({item['action']})")
    doc.body = doc.body.rstrip() + "\n".join(lines) + "\n"
    doc.status = "approved"
    save_spec_document(workspace_root, spec_name, doc)


def list_changes_for_spec(workspace_root, limit: int = 15) -> list[dict]:
    import json

    from pkf.workspace import Workspace

    ws = Workspace(workspace_root)
    changes = list_changes(ws, limit=50)
    session_path = pkf_dir(workspace_root) / "build_session.json"
    if session_path.exists():
        try:
            started_at = json.loads(session_path.read_text(encoding="utf-8"))["started_at"]
            changes = [c for c in changes if c.get("at", "") >= started_at]
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    return changes[-limit:]


def save_platform_spec(workspace_root, slug: str = "pkf-platform") -> str:
    """Atualiza spec da plataforma com capacidades atuais."""
    body = """# PKF — plataforma

## Capacidades

- Spec automática + pipeline compose (brainstorm → build → verify → review)
- Pool híbrido: **9Router primário** (OpenCode Free, combos) + **router nativo fallback**
- Pool de provedores nativo com **3 tiers** (subscription → cheap → free)
- **Multi-chave** por provedor (GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEYS)
- Compactação RTK de tool results (head/hash/tail)
- Web search nativo (Tavily ou Brave) via tool `web_search`
- PostgreSQL para sessões, mensagens, specs e tarefas
- Frontend Vite + React + Tailwind CSS
- Memória persistente: MEMORY.md, checkpoint.md, progresso por tarefa
- Busca de skills BM25 + skills frontend-design e python-toolchain
- Compactação de contexto por modelo (budget por provider)
- Árvore de tarefas T1/T2/T3 na UI
- Comando /goal com juiz independente pós-build
- Build paralelo com retry automático (até 2 tentativas)
- Changelog automático na spec após build
- Preview embutido e link externo

## Stack sugerida padrão

- frontend: HTML/CSS/JS ou React leve
- backend: Python FastAPI ou Node leve
- database: SQLite ou JSON local
- deploy: estático na VPS / Docker
"""
    doc = SpecDocument(
        title="PKF Platform",
        body=body,
        status="approved",
        suggested_stack={
            "frontend": "HTML/CSS/JS",
            "backend": "FastAPI",
            "database": "SQLite",
            "deploy": "Docker",
        },
        confirmed_stack={
            "frontend": "HTML/CSS/JS",
            "backend": "FastAPI",
            "database": "SQLite",
            "deploy": "Docker",
        },
    )
    save_spec_document(workspace_root, slug, doc)
    return slug
