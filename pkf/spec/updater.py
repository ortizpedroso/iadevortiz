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

## Visão

Assistente multiagente para especificar, implementar, revisar e testar software — com UI inspirada em Claude/Cursor (tema escuro, rail lateral, chat centralizado).

## Capacidades

- Pipeline **/spec → aprovação → /build → /review** com loop até aprovação
- UI Vite + React 19 + Tailwind 4: rail de ícones, painel de projeto, painel de spec, preview embutido
- Modal de autenticação (sem `prompt()`); token via `PKF_AUTH_TOKEN`
- Pool híbrido: **9Router primário** (OpenCode Free, NVIDIA NIM, combos) + **router nativo fallback**
- Pool de provedores nativo com **3 tiers** (subscription → cheap → free)
- **Multi-chave** por provedor (GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEYS)
- DeepSeek-R1 reasoning (architect, reviewer, logic)
- Compactação RTK de tool results (head/hash/tail)
- Web search nativo (Tavily ou 9Router `/v1/search`)
- PostgreSQL para sessões, mensagens, specs e tarefas
- Memória persistente: MEMORY.md, checkpoint.md, progresso por tarefa
- Busca de skills BM25 + skills frontend-design e python-toolchain
- Árvore de tarefas T1/T2/T3 na UI
- Comando /goal com juiz independente pós-build
- Build paralelo com retry automático (até 2 tentativas)
- Changelog automático na spec após build
- Headers de segurança (nosniff, frame-options, referrer-policy)
- Health `/api/health` reduzido sem autenticação

## UI / UX

- Paleta escura quente (#191919, accent #d97757)
- Tipografia: Inter (UI) + Source Serif 4 (títulos)
- Composer fixo estilo Claude; mensagens do usuário à direita
- Acessibilidade: skip link, `aria-live`, foco visível, `prefers-reduced-motion`
- SEO: meta description, theme-color, `noindex` na UI privada

## Stack sugerida padrão

- frontend: React + Vite + Tailwind
- backend: Python FastAPI + WebSocket
- database: PostgreSQL
- deploy: Docker Compose na VPS (:8765)
"""
    doc = SpecDocument(
        title="PKF Platform",
        body=body,
        status="approved",
        suggested_stack={
            "frontend": "React + Vite + Tailwind",
            "backend": "FastAPI",
            "database": "PostgreSQL",
            "deploy": "Docker Compose",
        },
        confirmed_stack={
            "frontend": "React + Vite + Tailwind",
            "backend": "FastAPI",
            "database": "PostgreSQL",
            "deploy": "Docker Compose",
        },
    )
    save_spec_document(workspace_root, slug, doc)
    return slug
