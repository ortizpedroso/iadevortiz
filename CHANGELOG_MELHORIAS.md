# Changelog — Melhorias PKF (auditoria honesta)

Documento reescrito na **Fase 0 (rodada 2)** para registrar tudo que mudou entre o commit anterior à rodada 1 e o HEAD atual — incluindo o que foi pedido, o que foi implementado além do pedido, e commits posteriores.

---

## Pendências finais — `fix/pendencias-rodada2`

**Data:** 2026-08-17

### Item 1 — Changelog retroativo do commit `444279f`

- **`pkf/config.py::default_provider()`**: removida condição `PKF_ENV == "production"` do fallback por chave de API — `groq`/`gemini`/etc. passam a ser considerados em qualquer ambiente; `ollama` só quando nenhuma chave existir.
- **`tests/test_platform_spec_rodada2.py`**: removido `test_platform_review_file_approved` — dependia de `.pkf/reviews/pkf-platform.md` (gitignored), falhava em clone limpo; cobertura mantida por `test_platform_spec_review_approved` (tmp_path).
- **`tests/test_platform_build_review_cycle.py`**: verificação **estática/determinística** (strings nos arquivos + `save_platform_spec`) — **não** é o ciclo real `/build`→`/review` via Router/agentes. Substituição nunca declarada antes; registrada aqui retroativamente.

### Item 2 — Código morto removido

- **`_auto_approve_spec()`** removida de `pkf/router.py` — confirmado via `grep` zero referências em `pkf/` e `tests/`.

### Item 3 — `sentence-transformers`/`numpy` fora de produção

- **`requirements-prod.txt`**: removidos `numpy` e `sentence-transformers`.
- **`requirements.txt`**: mantidos (dev/teste com modelo completo).
- **Produção**: `pkf/semantic_index.py` cai no embedder leve (`math` + hash) quando `sentence_transformers` não está instalado (`try/except` em `_get_model()`).

### Item 4 — Decisões fechadas (sem código novo)

- **Parte B** (pipeline `/build` v0.3.1, review-fix loop, planner LLM): **mantida** — testada e em produção.
- **Commit `14d1a09`** (biblioteca lateral): **mantido** — feature separada e funcional.
- **Fase 5 LangGraph**: stub nativo **mantido**; pacote `langgraph` real **não** instalado nesta rodada.

### Item 5 — Modelo OpenAI padrão

- **`pkf/config.py`**: default `OPENAI_MODEL` alterado de `gpt-4.1-mini` (aposentado 23/07/2026) para **`gpt-5.4-mini`**.

### Item 6 — Frontend em produção (UI menu/cores)

- **Causa provável**: imagem Docker servindo `frontend/dist` antigo — `frontend/dist` não vai pro git; rebuild da imagem necessário após `7a943bf`.
- **Correção**: `Dockerfile` recebe `ARG PKF_GIT_SHA`; `deploy/hostinger/update.sh` passa `git rev-parse HEAD` no build para invalidar cache do stage frontend a cada deploy.
- **Ação manual pós-merge**: `bash deploy/hostinger/update.sh` na VPS (rebuild + redeploy).

### Item 7 — Flash de projeto na sidebar

- **`frontend/src/App.tsx`**: boot não chama mais `applyLibrary(data.library)` de `/api/session` — só `loadLibrary()` popula chats/projetos (fonte única).

### Item 8 — Excluir projeto sem feedback

- **`frontend/src/App.tsx::deleteProject()`**: erro visível via mensagem `role: "error"`; sucesso usa `loadLibrary()` em vez de library embutida na resposta DELETE.

---

## Rodada 2 — Fase 6: Avaliação sandbox Docker (sem implementação)

**Data:** 2026-08-17  
**Decisão:** **não implementar** sandbox Docker para `run_command` nesta rodada.

### Comparativo

| Opção | Segurança | Latência | Complexidade | Recomendação |
|-------|-----------|----------|--------------|--------------|
| **(a) Allowlist atual** (`shlex`, sem shell, env filtrado) | Média — processo no host | **~ms** (melhor) | Já implementada | **Manter por ora** |
| **(b) Docker efêmero por comando** | Alta — isolamento | **+1–5s+** cold-start (pull ~40s na 1ª vez local) | Alta — pool pré-aquecido necessário | Adiar |
| **(c) Nada agora** | — | — | — | Rejeitado (já temos (a)) |

### Medição cold-start (ambiente dev Windows)

- `docker run --rm alpine echo ok` — pull inicial ~42s; execução subsequente seria mais rápida com imagem em cache.
- Na VPS Hostinger, estimar **1–3s** por container mínimo com imagem já presente; **inaceitável** por comando interativo sem pool.

### Observações

- Implementação Docker **fora de escopo** até decisão explícita do operador.
- Se avançar: preferir **pool de containers pré-aquecidos**, não cold-start por execução.

---

## Rodada 2 — Fase 5: Grafo de build piloto

**Data:** 2026-08-17  
**Escopo:** pipeline `/build` como grafo atrás de `PKF_USE_LANGGRAPH_BUILD=1`.

### Implementado

- `pkf/workflow/build_graph.py` — nós `plan → build (retry) → review (fix loop)`
- Flag `PKF_USE_LANGGRAPH_BUILD=1` em `Router._run_parallel_build()`
- **Sem pacote `langgraph`** — grafo async nativo (mesma semântica, biblioteca LangGraph real pendente de aprovação de dependência)

### Arquivos

- `pkf/workflow/build_graph.py`, `pkf/router.py`, `tests/test_build_graph.py`

### Testes

- **130 passed** total (+3 build_graph)

### Pendente

- Comparação lado a lado antigo vs. grafo via `scripts/benchmark.py --live` (modo live não implementado)
- Migrar para LangGraph oficial após aprovar `langgraph` no `requirements.txt`

---

## Rodada 2 — Fase 4: Harness de benchmark

**Data:** 2026-08-17

### Implementado

- `scripts/benchmark.py` — 2 specs fixas, saída tabela ou `--json`, modo mock (sem API)
- Baseline mock: `todo-html-basico` 0.005s, `api-crud-simples` 0.008s

### Arquivos

- `scripts/benchmark.py`, `tests/test_benchmark.py`

### Pendente

- Modo `--live` (ciclo real /build) — não implementado
- Integração CI — explicitamente fora de escopo

---

## Rodada 2 — Fase 3: Tier de qualidade (Claude)

**Data:** 2026-08-17

### Implementado

- `PKF_TIER_QUALITY` + `PKF_QUALITY_MODEL` em `config.py`
- Slot `tier=quality` em `build_provider_slots()`; `ProviderPool.get_client_for_agent()`
- Só `architect` e `reviewer` usam quality; build agents **nunca**
- Gateway via 9Router (`kr/claude-*`) documentado em `PKF.md`

### Arquivos

- `pkf/config.py`, `pkf/router_native.py`, `pkf/provider_pool.py`, `pkf/router.py`, `tests/test_quality_tier.py`, `PKF.md`

### Testes

- **125 passed** após Fase 3 (+5)

### Gateway

- 9Router suporta Claude (`kr/claude-sonnet-4.5` já testado). LiteLLM não verificado neste ambiente.

---

## Rodada 2 — Fase 2: 9Router como caminho padrão

**Data:** 2026-08-17  
**Escopo:** 9Router primeiro quando `NINEROUTER_URL` existe; skip proativo em 401/chave ausente; fallback nativo inalterado para outros erros.

### Implementado

- `ninerouter_should_skip()`, `is_ninerouter_auth_error()`, `ninerouter_auth_warning()` em `pkf/ninerouter.py`
- Chave ausente ou health `401`/`403` → 9Router **não entra** no pool nem em `default_provider()`
- Timeout/conexão recusada → comportamento anterior (9Router permanece no pool; rotação existente trata)
- `Router._warn_ninerouter_auth_if_needed()` emite aviso no boot (print)
- `PKF.md` atualizado: 9Router padrão sem `PKF_PROVIDER=ninerouter`; seção "Erro 401 no 9Router"

### Arquivos tocados

| Arquivo | Mudança |
|---------|---------|
| `pkf/ninerouter.py` | skip proativo + mensagem de correção |
| `pkf/router_native.py` | `_ninerouter_slot()` respeita skip |
| `pkf/config.py` | `default_provider()` e `provider_pool_names()` |
| `pkf/router.py` | aviso no boot |
| `PKF.md` | documentação |
| `tests/test_ninerouter.py` | +5 testes, 3 existentes ajustados |
| `tests/test_config.py` | mock de health no teste de produção |

### Testes

| Momento | Total |
|---------|-------|
| Após Fase 1 | 115 |
| Após Fase 2 | **120** (+5) |

### Latência (Fase 2)

| Medição | Resultado |
|---------|-----------|
| Skip com `NINEROUTER_KEY` ausente | instantâneo (sem HTTP) |
| `ninerouter_health()` com timeout 8s | até ~8s no pior caso (só quando chave presente); executado no boot, não por request |
| Boot com chave inválida (401) | 1–3 chamadas health no init do Router (aceitável; evita tentativa real de LLM) |

### Observações fora de escopo (Fase 2)

- Não alteramos `try_rotate_provider` além do skip proativo no pool.
- Não rodamos `fix-ninerouter-key.sh` nem editamos `.env` da VPS.

---

## Rodada 2 — Fase 1: Headroom proxy (opt-in)

**Data:** 2026-08-17  
**Escopo:** apontar `get_ai_client()` para proxy Headroom via configuração, sem alterar lógica de compressão.

### Implementado

- `headroom_proxy_url()` em `pkf/config.py` lê `PKF_HEADROOM_PROXY_URL`
- `get_ai_client()` usa a URL do proxy como `base_url` do `AsyncOpenAI` quando definida; `ProviderConfig.base_url` permanece o upstream real (Groq, Gemini, etc.)
- Sem a variável: comportamento idêntico ao anterior
- Documentação curta em `PKF.md` (seção Headroom) e comentário em `.env.example`
- **Nenhuma dependência nova** adicionada ao projeto (`headroom-ai` é instalado manualmente pelo operador)

### Arquivos tocados

| Arquivo | Mudança |
|---------|---------|
| `pkf/config.py` | `headroom_proxy_url()` |
| `pkf/providers.py` | `effective_base_url` via proxy |
| `PKF.md` | seção Headroom |
| `.env.example` | variável comentada |
| `tests/test_headroom_proxy.py` | 5 testes novos |

### Testes

| Momento | Total |
|---------|-------|
| Antes (Fase 0) | 110 |
| Após Fase 1 | **115** (+5) |

### Latência (Fase 1)

| Medição | Resultado |
|---------|-----------|
| Criação de client (`get_ai_client` × 200) sem proxy | ~instantâneo (< 500 ms total) |
| Criação de client com `PKF_HEADROOM_PROXY_URL` | delta < 200 ms vs. sem proxy |
| Chamada real via proxy Headroom | **não medida** — Headroom não estava rodando neste ambiente; medir manualmente após `headroom proxy --port 8787` |

### Observações fora de escopo (Fase 1)

- Instalação de `headroom-ai[proxy]` no Docker/VPS fica a cargo do operador (não alteramos `requirements.txt` nem `docker-compose.yml`).
- Compressão propriamente dita é responsabilidade do Headroom upstream.

---

## Escopo da auditoria (Fase 0)

| Referência | Commit | Descrição |
|------------|--------|-----------|
| **Baseline (pré-rodada 1)** | `0106db1` | fix: resolver frontend/dist via PKF_APP_ROOT no Docker |
| **Rodada 1** | `c2dcab1` | feat: pipeline build v0.3.1 e ferramentas de producao (fases 1-4) |
| **Pós-rodada 1** | `14d1a09` | feat: biblioteca lateral de chats e projetos com API REST |
| **HEAD atual** | `14d1a09` | mesmo commit acima |

Comando usado: `git diff 0106db1..HEAD --stat` → **36 arquivos**, **+2622 / −186 linhas**.

---

## Parte A — Pedido no prompt original da rodada 1 (Fases 1–4)

Itens abaixo correspondem ao prompt de confiabilidade/segurança/busca. Implementados no commit `c2dcab1`.

### Fase 1 — Confiabilidade do `edit_file` / `write_file`

- Detecção de trecho ambíguo (`old_string` duplicado sem `replace_all`)
- Erro quando `old_string == new_string`
- Validação de sintaxe pós-escrita (`.py` via `ast.parse`, `.json` via `json.loads`) com reversão automática
- Auditoria com `old`/`new` + `unified_diff` truncado no log de mudanças

**Arquivos:** `pkf/tools/impl.py`, `tests/test_tools_edit.py`, ajuste mínimo em `tests/test_improvements.py`

### Fase 2 — Lock de escrita entre agentes paralelos

- Lock por arquivo (`asyncio.Lock`) em `Workspace.file_lock()`
- `ToolRegistry.execute_async()` adquire lock antes de `write_file`/`edit_file`
- Evento `tool` com `info=aguardando lock em <arquivo>` quando lock ocupado
- Agentes usam `await tools.execute_async()` em `pkf/agents/base.py`

**Arquivos:** `pkf/workspace.py`, `pkf/tools/registry.py`, `pkf/agents/base.py`, `pkf/router.py`, `tests/test_tools_lock.py`

### Fase 3 — Sandbox para `run_command`

- Parse com `shlex.split()`; primeiro token validado contra allowlist
- Rejeição de encadeamento (`&&`, `;`, `|`, `` ` ``, `$(`, `>`, `<`)
- `subprocess.run(..., shell=False, cwd=workspace.root)`
- Ambiente filtrado (remove `*_API_KEY`, `*_TOKEN`, `*_SECRET`, `DATABASE_URL`)
- Timeout via `COMMAND_TIMEOUT`; saída truncada em ~10 KB
- Docstring atualizada em `TOOL_DEFINITIONS["run_command"]`

**Arquivos:** `pkf/tools/impl.py`, `pkf/tools/registry.py`, `tests/test_run_command.py`

### Fase 4 — Indexação semântica de código

- Módulo `pkf/semantic_index.py` com embeddings locais (`sentence-transformers/all-MiniLM-L6-v2`)
- Fallback leve via `PKF_TEST_SEMANTIC=1` (sem carregar modelo pesado nos testes)
- Chunks por função/classe (`.py`) ou blocos de ~80 linhas
- Índice em `.pkf/index/semantic.json`
- Reindexação incremental em `write_file`/`edit_file` (`update_file_index`)
- `search_code` estendido com parâmetro `mode: "text" | "semantic"`
- Busca textual/BM25 existente preservada (`mode=text` padrão)

**Arquivos:** `pkf/semantic_index.py`, `pkf/tools/impl.py`, `pkf/tools/registry.py`, `requirements.txt`, `tests/test_semantic_index.py`

---

## Parte B — Implementado além do pedido (commit `c2dcab1`)

Estes itens **não estavam** no prompt original das Fases 1–4 e **não constavam** na versão anterior deste changelog.

### Pipeline `/build` v0.3.1

- **`pkf/workflow/planner.py`**: `plan_build_llm()` (planner via LLM com fallback heurístico `plan_build()`), `group_tasks_into_phases()`, `plan_fix_tasks()`
- **`pkf/workflow/orchestrator.py`**: execução em fases ordenadas (`run_build_phases`), labels de progresso por fase, emissão de evento `active_agent` durante tarefas
- **`pkf/workflow/compose.py`**: `run_brainstorm()` pré-build, constante `HANDOFF_API_PATH = ".pkf/handoff/api.md"`, `MAX_REVIEW_FIX_CYCLES`
- **`pkf/workflow/review.py`** (arquivo novo): `parse_review_status()`, `load_latest_review()`, parsing de relatórios `APROVADO`/`REPROVADO`
- **`pkf/workflow/cycle.py`**, **`pkf/workflow/tasks.py`**: ajustes menores alinhados ao pipeline em fases
- **`pkf/router.py`**: `_run_parallel_build()` reescrito — brainstorm → planner LLM → fases → verify → **loop review→fix** (até `PKF_REVIEW_FIX_CYCLES`), retry por agente (`PKF_BUILD_RETRIES`), emissão WebSocket `active_agent`/`plan`/`task_progress`
- **`tests/test_workflow_build.py`** (arquivo novo): testes do planner e do parser de review

### Configuração e versão

- **`pkf/config.py`**: `MAX_REVIEW_FIX_CYCLES`, `agent_provider_override()` (`PKF_<AGENT>_PROVIDER`)
- **`pyproject.toml`**: versão `0.3.0` → `0.3.1`
- **`pkf/spec/updater.py`**: spec da plataforma atualizada descrevendo pipeline em fases, review-fix loop, handoff API (texto de spec, não código de runtime)

### Frontend (rodada 1)

- **`frontend/src/App.tsx`**: indicador no header com agente ativo · provider · modelo (estados `activeAgent`/`activeProvider`, evento WS `active_agent`)
- **`frontend/src/types.ts`**: campos `active_agent` em `SessionSnapshot`

### Prompts

- **`pkf/agents/prompts.py`**: formato obrigatório de relatório do reviewer (`Status: APROVADO` / `REPROVADO`)

### Dependências adicionadas **sem confirmação explícita** (incidente)

- **`requirements.txt`**: `numpy>=1.26.0`, `sentence-transformers>=3.0.0` (dev/teste — embeddings completos)
- **`requirements-prod.txt`**: **sem** `numpy`/`sentence-transformers` — produção usa fallback leve de `semantic_index.py` (decisão fechada em `fix/pendencias-rodada2`)

---

## Parte C — Commit posterior `14d1a09` (fora da rodada 1)

Implementação de **biblioteca lateral** (chats/projetos), solicitada em sessão separada — **não faz parte** do prompt original da rodada 1.

### Backend

- **`pkf/web/library.py`** (novo): CRUD chats/projetos em modo arquivo e PostgreSQL; migração de `current.json` legado; validação de slug/chat_id
- **`pkf/db/repository.py`**: `list_user_chats`, `list_user_projects`, `activate_chat_session`, `attach_chat_to_project`, `delete_chat_session`, `delete_project_record`
- **`pkf/web/history.py`**: multi-chat file mode, `active_chat_id`, `replace_messages()`
- **`pkf/web/server.py`**: endpoints `/api/library`, `/api/chats`, `/api/projects/{slug}`, integração com sessão
- **`pkf/router.py`**: `restore_chat_history()` — reidrata contexto nos agentes após troca de chat

### Frontend

- **`frontend/src/components/Sidebar.tsx`**: seções Chats e Projetos (criar, selecionar, excluir, anexar)
- **`frontend/src/App.tsx`**: handlers de library, `replaceSpec` ao trocar chat/projeto, reset de preview
- **`frontend/src/types.ts`**: `ChatItem`, `ProjectItem`, `LibrarySnapshot`

### Spec e docs

- **`PKF.md`**, **`pkf/spec/updater.py`**: documentação da biblioteca lateral e tabela de endpoints

### Dependências em produção **sem confirmação explícita** (incidente repetido)

- **`requirements-prod.txt`**: ~~`numpy`~~, ~~`sentence-transformers`~~ — removidos em `fix/pendencias-rodada2` (fallback leve em prod)

### Testes novos (commit `14d1a09`)

- `tests/test_library.py`, `tests/test_library_spec.py`, `tests/test_router_history.py`

---

## Contagem de testes

| Momento | Commit | Testes (`pytest -q`) |
|---------|--------|----------------------|
| Pré-rodada 1 | `0106db1` | **70** |
| Após rodada 1 | `c2dcab1` | **95** (+25) |
| HEAD atual | `14d1a09` | **110** (+15) |

Rodar hoje: `pytest tests/ -q` → **110 passed**.

---

## Código morto reportado (Fase 0)

| Símbolo | Arquivo | Situação |
|---------|---------|----------|
| ~~`_auto_approve_spec()`~~ | ~~`pkf/router.py`~~ | **Removido** em `fix/pendencias-rodada2` |

---

## Decisões pendentes (aguardam sua revisão)

~~Itens abaixo fechados em `fix/pendencias-rodada2` — ver seção "Pendências finais".~~

1. ~~**Manter ou reverter a Parte B**~~ → **Mantida**
2. ~~**Manter `sentence-transformers` em `requirements-prod.txt`**~~ → **Removido de prod; mantido em dev**
3. ~~**Manter commit `14d1a09`**~~ → **Mantido**
4. ~~**LangGraph real**~~ → **Stub nativo mantido; pacote não instalado**

---

## Próximos passos (rodada 2 — prompt atual, ainda não implementados)

Referência apenas; **não implementado nesta Fase 0**:

- Fase 1: Headroom proxy opt-in (`PKF_HEADROOM_PROXY_URL`)
- Fase 2: 9Router como caminho padrão com health check proativo
- Fase 3: Tier de qualidade (`PKF_TIER_QUALITY`) só para `architect`/`reviewer`
- Fase 4: Harness `scripts/benchmark.py`
- Fase 5: LangGraph piloto (`PKF_USE_LANGGRAPH_BUILD=1`)
- Fase 6: Avaliação sandbox Docker (sem implementação)

---

## Observações fora de escopo (Fase 0)

- Deploy VPS do commit `14d1a09` foi interrompido localmente (build Docker longo); push para `origin/main` concluído.
- Nenhum arquivo de código foi alterado nesta Fase 0 — **somente este changelog**.
