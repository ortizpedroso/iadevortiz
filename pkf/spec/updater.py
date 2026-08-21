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

Assistente multiagente para especificar, implementar, revisar e testar software — UI tema escuro (sidebar lateral, chat centralizado, variáveis CSS `--pkf-*`).

## Capacidades

- Pipeline **/spec → aprovação manual → /build → review→fix loop** até aprovação
- **Duas implementações de /build**:
  - **Clássica** (padrão): fases backend → logic → frontend → tester, brainstorm, juiz /goal, changelog
  - **Grafo piloto** (`PKF_USE_LANGGRAPH_BUILD=1`): plan → build → review em `build_graph.py`
- **Build em fases**: backend → logic → frontend → tester (dependências respeitadas)
- **Planner LLM** com fallback heurístico por keywords na spec
- **Handoff API**: backend documenta `.pkf/handoff/api.md` → frontend consome
- **Retry inteligente**: reexecuta só agentes que falharam (até `PKF_BUILD_RETRIES`)
- **Review→fix loop**: até `PKF_REVIEW_FIX_CYCLES` ciclos automáticos pós-build
- UI Vite + React 19 + Tailwind 4: rail, painel spec, preview, indicador agente/provider
- **Biblioteca lateral**: listagem de chats e projetos — criar, ativar, excluir (individual ou em massa), anexar chat↔projeto
- Modal de autenticação (`PKF_AUTH_TOKEN`); health público reduzido
- **OmniRoute router-only** (`PKF_ROUTER_ONLY=1`): gateway único — tokens só do dashboard OmniRoute/9Router, sem `GROQ_API_KEY`/`GEMINI_API_KEY` no pool
- Pool híbrido opcional (`PKF_ROUTER_ONLY=0`): **9Router/OmniRoute primário** + router nativo fallback
- Skip proativo 9Router/OmniRoute em **401/chave ausente** — aviso no boot; em router-only não há fallback Groq/Gemini
- **Headroom proxy** opt-in (`PKF_HEADROOM_PROXY_URL`) — compressão de contexto via proxy OpenAI-compatible
- **Tier de qualidade** (`PKF_TIER_QUALITY`) — Claude via 9Router/gateway só para `architect` e `reviewer`
- **Build grafo piloto** (`PKF_USE_LANGGRAPH_BUILD=1`) — pipeline /build alternativo em `build_graph.py`
- **Benchmark interno** (`scripts/benchmark.py`) — specs de referência, saída JSON/tabela (mock)
- **Provider/modelo por agente** via `PKF_<AGENT>_PROVIDER` e `PKF_<AGENT>_MODEL`
- DeepSeek-R1 reasoning (architect, reviewer, logic)
- PostgreSQL, memória persistente, skills BM25, juiz /goal
- Headers de segurança; changelog automático na spec após build
- **Verificação T3 persistida** (`.pkf/last_verify.json`) + ferramenta `get_last_verification` para respostas fundamentadas pós-build
- **Saudações locais** (`oi`, `olá`) sem chamar gateway de IA
- **Classificador de intenção**: perguntas conversacionais (`você consegue…`, `dá pra…`) tratadas antes de `FEATURE_HINTS`; fallback LLM só quando keywords não resolvem
- **Arquiteto entrevista**: uma pergunta por vez; sem `save_spec` até objetivo, requisitos, restrições e critério de “concluído” claros; pedido já detalhado pode ir direto à spec
- **Memória de sessão**: índice `.pkf/memory/index.json`; match por **proporção** de sobreposição (≥45%, mín. 3 termos) com stopwords de domínio (`sistema`, `projeto`, `quero`, `desenvolver`, …) para evitar falso-positivo entre projetos parecidos
- **Agentes de memória**: restaurados com `project_context`, `list_dir`, `read_file`, `search_code`; prompt exige checar o workspace atual antes de afirmar que algo está implementado — resumo antigo não é estado atual
- **Compactação de contexto**: `compact_messages_llm` (resumo estruturado) com fallback mecânico quando o gateway falha

## Segurança e produção

- **`PKF_AUTH_TOKEN`**: obrigatório e forte em `PKF_ENV=production` (boot falha se ausente/fraco); deploy **não sobrescreve** token existente
- **Preview isolado**: iframe sem `allow-same-origin`; URLs de preview **sem** token; CSP em preview e shell
- **`/api/health` público**: só `{ok, auth_required}`; metadados completos apenas autenticado
- **WebSocket**: rejeita conexão antes de `accept` se token inválido
- **`run_command`**: desabilitado em produção salvo `PKF_ALLOW_RUN_COMMAND=1`
- **Deploy**: `NINEROUTER_MODEL` só definido na 1ª instalação (`set_kv_default`); URLs pós-deploy **não** imprimem token
- **Respostas pós-build**: `generalista`/`reviewer` consultam `get_last_verification` antes de hipóteses sobre falha T3
- **Ambiguidade na spec**: agentes `frontend`/`backend`/`logic` param implementação e reportam conflito antes de codificar
- **Memória**: agente de memória nunca afirma “já pronto” sem `list_dir`/`read_file`; projeto vazio deve ser declarado explicitamente

## Ferramentas de confiabilidade (rodada 1)

- `edit_file`/`write_file`: validação sintaxe, diff auditado, lock por arquivo
- `run_command`: sandbox shlex, allowlist, env filtrado; bloqueado em produção por padrão
- `search_code`: modo semântico (`mode=semantic`) via índice local
- `get_last_verification`: último resultado real da fase Verificação (T3)

## Fluxo /build

1. Brainstorm (architect, sem código)
2. Planner (LLM ou heurística) → fases ordenadas
3. Implementação em fases com handoff API
4. Verificação de arquivos + retry por agente
5. Loop review → correção → review até **Status: APROVADO**
6. Juiz independente (/goal) + resposta amigável na UI

## UI / UX

- **Sidebar esquerda**: seções Projetos e Conversas
- **Projetos**: Menu de contexto ⋯ (fixar, renomear, excluir) + modo **Selecionar** para excluir vários ou todos
- **Conversas**: Menu de contexto ⋯ (vincular projeto, excluir chat)
- **Tema escuro PKF**: variáveis CSS (`--pkf-bg-primary`, `--pkf-accent`, etc.), sidebar e painéis escuros
- Indicador no header: agente ativo · provider · modelo
- Acessibilidade: skip link, aria-live, `:focus-visible` com acento

## API biblioteca

| Endpoint | Função |
|---|---|
| `GET /api/library` | Lista chats e projetos |
| `POST /api/chats` | Novo chat |
| `POST /api/chats/{id}/activate` | Ativa chat e carrega mensagens |
| `DELETE /api/chats/{id}` | Exclui chat |
| `POST /api/chats/{id}/attach` | Anexa ou desanexa projeto |
| `POST /api/projects/{slug}/activate` | Ativa projeto |
| `PATCH /api/projects/{slug}` | Renomeia nome de exibição (slug inalterado) |
| `DELETE /api/projects/{slug}` | Exclui um projeto |
| `POST /api/projects/bulk-delete` | Exclui vários (`slugs`) ou todos (`all: true`) |
| `POST /api/projects/{slug}/pin` | Fixa/desafixa projeto |

## Configuração (rodada 2)

| Variável | Função |
|---|---|
| `PKF_ROUTER_ONLY` | `1` = só OmniRoute/9Router (pool `ninerouter`); `0` = híbrido com chaves diretas |
| `ROUTER_IMAGE` | Imagem Docker do gateway (padrão `diegosouzapw/omniroute:latest`) |
| `PKF_HEADROOM_PROXY_URL` | Proxy Headroom (opt-in) |
| `NINEROUTER_URL` | OmniRoute/9Router como primário automático |
| `NINEROUTER_KEY` | Chave sk-... do dashboard OmniRoute |
| `PKF_TIER_QUALITY` | Provedor tier qualidade (ex.: `ninerouter`) |
| `PKF_QUALITY_MODEL` | Modelo Claude (ex.: `kr/claude-sonnet-4.5`) |
| `PKF_USE_LANGGRAPH_BUILD` | `1` = pipeline /build via grafo piloto |
| `PKF_ALLOW_RUN_COMMAND` | `1` = permite `run_command` em produção |
| `PKF_RELEVANCE_THRESHOLD` | Proporção mínima (padrão `0.45`) para rotear mensagem a agente de memória |
| `PKF_MEMORY_MIN_OVERLAP` | Mínimo de termos significativos em comum (padrão `3`) no match de memória |
| `PKF_NINEROUTER_MODEL_CHAIN` | Cadeia de fallback de modelos no gateway OmniRoute |

## Stack

- frontend: React + Vite + Tailwind
- backend: Python FastAPI + WebSocket
- database: PostgreSQL
- deploy: Docker Compose (:8765) + OmniRoute (:20128 localhost, volume `/app/data`)
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
