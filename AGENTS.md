# AGENTS.md — PKF

Guia para agentes de código (Cursor, Cloud Agent, etc.) que trabalham neste repositório.

## Visão geral

PKF é uma plataforma multiagente (Python/FastAPI + React) para **especificar, implementar, revisar e testar** software em ciclo `/spec → /build → /review`. A UI roda em `:8765`; o gateway de IA (OmniRoute/9Router) em `:20128` na VPS.

Prompts de agente (`pkf/agents/prompts.py`) definem comportamento por papel — **não duplique** `CYCLE_RULES` nem `CRITICAL_RULES` aqui; consulte esse arquivo ao implementar lógica de agente.

---

## Comandos

| Ação | Comando |
|------|---------|
| Testes backend | `python3 -m pytest tests/ -q` |
| Lint Python | `python3 -m ruff check pkf tests` |
| UI local | `python -m pkf --ui` (ou `PKF_NO_BROWSER=1 python -m pkf --ui`) |
| Frontend dev | `cd frontend && npm install && npm run dev` |
| Frontend build | `cd frontend && npm run build` |
| Deploy VPS | `cd /opt/pkf && git pull origin main && bash deploy/hostinger/update.sh` |

---

## Arquitetura (pipeline)

1. **`/spec`** — arquiteto entrevista, `save_spec`, aprovação manual na UI.
2. **`/build`** — planner DAG (`depends_on`) → ordenação topológica (`run_build_dag`, `asyncio.gather` por grau zero) → handoff compacto entre agentes → verificação T3 → loop review→fix.
3. **`/review`** — revisor compara código com spec (escopo BFS via `impact_graph` quando há mutações), `save_review`, status APROVADO/REPROVADO.

Orquestrador: `pkf/workflow/orchestrator.py` (`run_build_dag`). Grafo piloto LangGraph opcional: `PKF_USE_LANGGRAPH_BUILD=1`. Coordenação entre agentes: **handoff** (`pkf/workflow/handoff.py`) — sem pub/sub PostgreSQL.

Estado de execução local fica em **`.pkf/`** (specs, reviews, tasks, `last_verify.json`) — **gitignored**, nunca versionar.

---

## Regra de escopo

- Implemente **somente** o que foi pedido; não toque arquivos fora do escopo.
- Não instale dependência nova sem perguntar / sem justificativa no changelog.
- Não invente requisito de produto — se ambíguo, pare e pergunte (ver `CRITICAL_RULES` e `IMPLEMENTATION_AMBIGUITY` em `prompts.py`).
- Deploy: **não sobrescreva** `PKF_AUTH_TOKEN`, `NINEROUTER_MODEL` nem config manual no `.env` (`set_kv_default`, não `sed` incondicional).

---

## Regra de testes

**Nunca simplifique ou substitua um teste para fazê-lo passar.** Se um teste falha, corrija o código, não o teste.

Antes de commitar, rode **`python3 -m ruff check pkf tests`** e **`python3 -m pytest tests/ -q`** — a CI executa os dois; só `pytest` local não pega erros de lint.

Se uma verificação real não puder ser automatizada (ex.: ciclo `/build`→`/review` completo via Router+LLM), declare explicitamente que o teste é **substituição estática/determinística** — nunca apresente como equivalente ao fluxo real (`tests/test_platform_build_review_cycle.py` documenta isso).

---

## Changelog

Toda mudança relevante exige entrada em **`CHANGELOG_MELHORIAS.md`** com:

- problema / contexto real;
- o que mudou (trecho ou diff como evidência);
- Definition of Done com checkboxes;
- resultado de `pytest tests/ -q` quando aplicável.

Não escreva só “atualizei X”.

**Documentação de arquitetura:** mudanças que alterem schema de banco (`pkf/db/models.py`), endpoints (`pkf/web/server.py`), ou fluxo de roteamento/orquestração (`pkf/router.py`, `pkf/workflow/`) devem atualizar `docs/ARQUITETURA.md` como parte do DoD — mesma disciplina aplicada a este changelog.

---

## Git e entrega

1. Branch `cursor/<descricao>` a partir de `main`.
2. Commits por tarefa lógica, mensagens claras.
3. Push → PR → CI verde.
4. Merge automático **só** se fast-forward limpo; senão, deixe o link do PR para revisão humana.

---

## Regras já formalizadas nesta sessão (referência rápida)

Consolidado de `CHANGELOG_MELHORIAS.md` — não inventar além disso:

| Tema | Regra |
|------|-------|
| Classificador | Perguntas conversacionais antes de `FEATURE_HINTS`; arquiteto não cria spec vazia |
| Build paralelo | DAG: `backend`+`logic` em grau zero; `frontend` após deps; `tester` após frontend; handoff substitui histórico bruto |
| Gateway | Saudações locais sem LLM; `get_last_verification` antes de hipóteses sobre falha T3 |
| OmniRoute | `NINEROUTER_MODEL` só default na 1ª instalação |
| Produção | Token forte obrigatório; preview sem `allow-same-origin`; health público mínimo |
| Token fraco | `migrate_weak_auth_token` no deploy — `teste123` não sobrevive em produção |

Detalhes completos: ler `CHANGELOG_MELHORIAS.md` do início ao fim antes de mudanças arquiteturais.

---

## Onde não mexer sem pedido explícito

- `docker-compose.yml` senhas padrão (documentadas, mudança separada).
- `DEPLOY.md` / `PKF.md` — alinhar só quando a tarefa pedir docs.
- Skills em `pkf/skills/` — carregados sob demanda, não duplicar no AGENTS.md.
