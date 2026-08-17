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

- Pipeline **/spec → aprovação manual → /build → review→fix loop** até aprovação
- **Build em fases**: backend → logic → frontend → tester (dependências respeitadas)
- **Planner LLM** com fallback heurístico por keywords na spec
- **Handoff API**: backend documenta `.pkf/handoff/api.md` → frontend consome
- **Retry inteligente**: reexecuta só agentes que falharam (até `PKF_BUILD_RETRIES`)
- **Review→fix loop**: até `PKF_REVIEW_FIX_CYCLES` ciclos automáticos pós-build
- UI Vite + React 19 + Tailwind 4: rail, painel spec, preview, indicador agente/provider
- **Biblioteca lateral**: listagem de chats e projetos — criar, ativar, excluir, anexar chat↔projeto
- Modal de autenticação (`PKF_AUTH_TOKEN`); health público reduzido
- Pool híbrido: **9Router primário por padrão** (quando `NINEROUTER_URL` definida) + **router nativo fallback**
- Skip proativo 9Router em **401/chave ausente** — aviso no boot, fallback Groq/Gemini
- **Headroom proxy** opt-in (`PKF_HEADROOM_PROXY_URL`) — compressão de contexto via proxy OpenAI-compatible
- **Tier de qualidade** (`PKF_TIER_QUALITY`) — Claude via 9Router/gateway só para `architect` e `reviewer`
- **Build grafo piloto** (`PKF_USE_LANGGRAPH_BUILD=1`) — pipeline /build alternativo em `build_graph.py`
- **Benchmark interno** (`scripts/benchmark.py`) — specs de referência, saída JSON/tabela (mock)
- **Provider/modelo por agente** via `PKF_<AGENT>_PROVIDER` e `PKF_<AGENT>_MODEL`
- DeepSeek-R1 reasoning (architect, reviewer, logic)
- PostgreSQL, memória persistente, skills BM25, juiz /goal
- Headers de segurança; changelog automático na spec após build

## Fluxo /build

1. Brainstorm (architect, sem código)
2. Planner (LLM ou heurística) → fases ordenadas
3. Implementação em fases com handoff API
4. Verificação de arquivos + retry por agente
5. Loop review → correção → review até **Status: APROVADO**
6. Juiz independente (/goal) + resposta amigável na UI

## UI / UX

- **Sidebar esquerda**: seções Chats e Projetos (criar, selecionar, excluir, anexar projeto ao chat)
- Indicador no header: agente ativo · provider · modelo
- Paleta escura (#191919, accent #d97757)
- Acessibilidade: skip link, aria-live, reduced motion

## API biblioteca

| Endpoint | Função |
|---|---|
| `GET /api/library` | Lista chats e projetos |
| `POST /api/chats` | Novo chat |
| `POST /api/chats/{id}/activate` | Ativa chat e carrega mensagens |
| `DELETE /api/chats/{id}` | Exclui chat |
| `POST /api/chats/{id}/attach` | Anexa ou desanexa projeto |
| `POST /api/projects/{slug}/activate` | Ativa projeto |
| `DELETE /api/projects/{slug}` | Exclui projeto |

## Configuração (rodada 2)

| Variável | Função |
|---|---|
| `PKF_HEADROOM_PROXY_URL` | Proxy Headroom (opt-in) |
| `NINEROUTER_URL` | 9Router como primário automático |
| `NINEROUTER_KEY` | Chave sk-... do dashboard 9Router |
| `PKF_TIER_QUALITY` | Provedor tier qualidade (ex.: `ninerouter`) |
| `PKF_QUALITY_MODEL` | Modelo Claude (ex.: `kr/claude-sonnet-4.5`) |
| `PKF_USE_LANGGRAPH_BUILD` | `1` = pipeline /build via grafo piloto |

## Ferramentas de confiabilidade (rodada 1)

- `edit_file`/`write_file`: validação sintaxe, diff auditado, lock por arquivo
- `run_command`: sandbox shlex, allowlist, env filtrado
- `search_code`: modo semântico (`mode=semantic`) via índice local

## Stack

- frontend: React + Vite + Tailwind
- backend: Python FastAPI + WebSocket
- database: PostgreSQL
- deploy: Docker Compose (:8765) + 9Router (:20128 localhost)
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
