# Changelog — Melhorias PKF (auditoria honesta)

Documento reescrito na **Fase 0 (rodada 2)** para registrar tudo que mudou entre o commit anterior à rodada 1 e o HEAD atual — incluindo o que foi pedido, o que foi implementado além do pedido, e commits posteriores.

---

## Paralelismo real: backend + logic na mesma fase

**Data:** 2026-08-21

### Por que backend e logic rodam juntos

Backend (API/persistência) e logic (regras de negócio) não têm dependência sequencial entre si — ambos leem a spec e escrevem em nós distintos do grafo. O `orchestrator.py` já executava tarefas da mesma fase em paralelo via `asyncio.gather`; o gargalo era `_assign_phases`, que colocava cada agente em fase diferente.

Concorrência de escrita no mesmo arquivo continua protegida pelo `file_lock` em `pkf/workspace.py` (rodada 1).

### Por que frontend e tester continuam sequenciais

- **Frontend** depende do contrato de API documentado pelo backend (`HANDOFF_API_PATH`).
- **Tester** depende do código implementado pelos agentes anteriores.

### Mudança

**Antes:**

```python
PHASE_ORDER = ("backend", "logic", "frontend", "tester")
# _assign_phases: um índice de fase por agente
```

**Depois:**

```python
PHASE_GROUPS = (
    ("backend", "logic"),
    ("frontend",),
    ("tester",),
)
# _assign_phases: índice = grupo em PHASE_GROUPS
```

Labels de UI em `orchestrator.py` adaptam-se aos agentes presentes na fase 0 (backend só, logic só, ou ambos).

### Definition of Done

- [x] `PHASE_GROUPS` substitui agrupamento serial; specs sem `logic` inalteradas
- [x] Backend+logic → mesma fase, 2 tarefas; teste de `asyncio.gather` com mock
- [x] Frontend e tester em fases separadas, depois
- [x] `orchestrator.py` só alterado para labels de UI

### Testes

`python3 -m pytest tests/ -q` → **179 passed** (após esta mudança)

---

## Integração PKF → Caddy compartilhado (eventosbr)

**Data:** 2026-08-20

### Por que mudou

A VPS já tem Caddy (`eventosbr-caddy-1`) dono das portas 80/443, usado por `eventosbr` e `sigep-forca`. Subir nginx/certbot próprio no PKF conflita com essa infra. O PKF passa a usar o **mesmo padrão do sigep-forca**: hook que conecta o container do PKF à rede Docker do Caddy e acrescenta um bloco marcado no Caddyfile compartilhado.

### Tarefas

1. **`deploy/hook-eventosbr-caddy.sh`** — espelha o hook do sigep-forca; marcador `# PKF —`; `reverse_proxy pkf-pkf-1:8765`; exige `PKF_HOST_DOMAIN`.
2. **Porta 8765** — bind `127.0.0.1:8765:8765` (não pública); removido `sed` que abria a porta no `update.sh`.
3. **`update.sh`** — chama o hook após health check se `PKF_HOST_DOMAIN` estiver no `.env`; aviso e continua se ausente.
4. **`/favicon.ico`** — rota pública no `AuthMiddleware` (corrige 401/500 sem token).

### Limitação documentada

O hook só roda no deploy do PKF. Se o `eventosbr` resetar o Caddyfile depois, o bloco do PKF some até o próximo deploy do PKF — limitação herdada do padrão sigep-forca, documentada em `PKF.md`.

### Definition of Done

- [x] `deploy/hook-eventosbr-caddy.sh` criado, marcador próprio `# PKF —`
- [x] Porta 8765 não é mais pública
- [x] `update.sh` chama hook condicionalmente
- [x] Fix favicon aplicado
- [x] Limitação documentada no `PKF.md`

### Testes

`python3 -m pytest tests/ -q` → **175 passed**

---

## Fix: flicker sidebar + cadeia OpenAI

**Data:** 2026-08-20

### Tarefa 1 — Boot sem fonte duplicada de projetos/chats

**Problema:** o boot chamava `applyLibrary(data.library)` na resposta de `/api/session` e em seguida `loadLibrary()` — duas fontes, com possível flash de projeto obsoleto antes da lista correta.

**Antes (`frontend/src/App.tsx`):**

```tsx
applySession(data.session, true);
setMessages(data.messages || []);
applyLibrary(data.library);
sessionBootstrappedRef.current = true;
// ...
if (!sessionBootstrappedRef.current) {
  await loadLibrary();
} else {
  await loadLibrary();
}
```

**Depois:**

```tsx
applySession(data.session, true);
setMessages(data.messages || []);
sessionBootstrappedRef.current = true;
// ...
await loadLibrary();
```

A sessão continua vindo de `/api/session` (mensagens, chat ativo, token). Projetos/chats vêm **só** de `loadLibrary()`.

**Contexto:** `applyLibrary(data.library)` no boot foi reintroduzido no commit `7cf2587` (PR #4 — sidebar estilo Claude), sobrepondo o fix da rodada 2.

### Tarefa 2 — Cadeia OpenAI com modelo mais recente primeiro

**Antes (`pkf/config.py`):**

```python
model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_OPENAI_MODEL_CHAIN = ("gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo")
```

**Depois:**

```python
model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
_OPENAI_MODEL_CHAIN = ("gpt-5.4-mini", "gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo")
```

`fallback_model_on_rate_limit()` **não alterado** — só a cadeia de 404 (`fallback_model_on_not_found`).

### Definition of Done

- [x] Boot de `App.tsx` usa `loadLibrary()` como única fonte da lista de projetos/chats
- [x] `if/else` redundante simplificado para `await loadLibrary()` direto
- [x] `_OPENAI_MODEL_CHAIN` começa com `gpt-5.4-mini`, demais mantidos como fallback
- [x] Default de `OPENAI_MODEL` atualizado para `gpt-5.4-mini`

### Testes

`python3 -m pytest tests/ -q` → **175 passed**

---

## Leva OmniRoute / WebSocket / CI — auditoria retroativa

**Período:** 2026-08-19 → 2026-08-20  
**Baseline:** `8dceda9` (`ci: deploy automatico na VPS via GitHub Actions em push na main`)  
**HEAD auditado:** `8ad1fb7` (`feat: OmniRoute 100% automático — usuário não vê provedores`)  
**Escopo:** `git log --oneline 8dceda9..HEAD` → **41 commits** (inclui merges de PRs #2–#14)  
**Diff total:** `git diff --stat 8dceda9..HEAD` → **98 arquivos**, **+2620 / −730 linhas**  
**Testes (Fase 1 e Fase 4):** `python3 -m pytest tests/ -q` → **175 passed in ~5–7s**

> Esta seção é **somente documentação**. Nenhum arquivo de código foi alterado nesta auditoria.

### Resumo da leva

Três eixos principais convergem nesta faixa de commits:

1. **OmniRoute router-only e automático** — produção passa a usar só o gateway (`PKF_ROUTER_ONLY=1`, pool `["ninerouter"]`); provedores free são registrados via script no deploy, sem dashboard manual; rotação de modelos no 429 via `ninerouter_model_chain()`.
2. **Estabilidade WebSocket + auth + fallback HTTP** — série de correções no lifecycle React (`App.tsx`), handshake de token, separação boot HTTP vs conexão WS, e `POST /api/message` quando o navegador não sustenta WebSocket.
3. **CI paralelo ao deploy** — novo `.github/workflows/ci.yml` (ruff + pytest + build frontend) roda em push/PR na `main`; `deploy.yml` continua responsável só pelo SSH + `update.sh` na VPS.

Commits intermediários (PRs #6–#10) trouxeram correções de modelo OpenAI/Gemini, UI estilo Claude, bulk delete de projetos e delete de chat — fora do escopo OmniRoute/WS, mas dentro dos 41 commits.

---

### Commits agrupados por tema

#### A — OmniRoute router-only e automático

| Commit | Mensagem |
|--------|----------|
| `6790742` | feat: OmniRoute router-only mode with efficient gateway defaults |
| `fbcb5d4` | fix: keep PKF online in router-only without gateway key |
| `4dd89b6` | fix: OmniRoute first-run onboarding and PKF WebSocket auth UX |
| `d5130fa` | fix: OmniRoute key bootstrap with cookie jar and anonymous fallback |
| `b3e320c` | feat: OmniRoute router-only mode e correções de UI/WebSocket |
| `31d71f1` | feat: OmniRoute 100% automático — sem dashboard para o usuário |
| `c4a1ad1` | fix: parênteses em is_ninerouter_client (ruff RUF021) |
| `9b47339` | Fix Gemini retired model and auto-configure 9Router on deploy |

**Arquivos centrais:** `pkf/config.py`, `pkf/ninerouter.py`, `pkf/router_native.py`, `pkf/provider_errors.py`, `pkf/errors.py`, `deploy/hostinger/setup-omniroute-providers.sh` (novo), `deploy/hostinger/set-env-keys.sh`, `deploy/hostinger/fix-ninerouter-key.sh`, `deploy/hostinger/update.sh`, `.env.production.example`, `docker-compose.yml`

#### B — WebSocket, autenticação e fallback HTTP

| Commit | Mensagem |
|--------|----------|
| `6685f1a` | fix: WebSocket auth handshake and stop reconnect without valid session |
| `00f00c0` | fix: stop auth login loop and normalize Bearer token input |
| `6703c98` | fix: stabilize WebSocket connection on UI boot |
| `d4b2045` | fix(frontend): corrige tela em branco por ReferenceError nos refs |
| `f147581` | fix: estabiliza WebSocket no navegador (1006/reconexão) |
| `58849b5` | fix: fallback HTTP quando WebSocket falha no navegador |
| `be33ece` | fix: fallback HTTP quando WebSocket falha no navegador |
| `4a3ac31` | fix: reconexão WebSocket mais estável e retry automático |
| `8545263` | fix: reconexão WebSocket estável + retry automático |
| `5583d2a` | fix: restaura rota / e favicon 204 |

**Arquivos centrais:** `frontend/src/App.tsx`, `frontend/src/lib/api.ts`, `frontend/src/main.tsx`, `pkf/web/server.py`, `pkf/web/auth.py`

#### C — CI e qualidade

| Commit | Mensagem |
|--------|----------|
| `571a49e` | Fix audit issues: tests, lint, CI, and version alignment |
| `3cfd42c` | fix(tests): corrige lint ruff para passar no CI |
| `ae9c378` | fix(tests): usa Path.read_text para passar ruff SIM115 |
| `e90e5f2` | fix: corrige if: invalido no workflow de deploy (secrets em if) |

**Arquivo novo:** `.github/workflows/ci.yml`

#### D — UI, modelos e biblioteca (PRs #6–#10, mesma faixa)

| PR / commit | Tema |
|-------------|------|
| `#6` `cd82093` / `d820678` | Default OpenAI `gpt-4o-mini`; rotação em 404 |
| `#7` `7cf2587` | Sidebar estilo Claude; fix flash de sessão no reload |
| `#8` `0ef7e80` | UI clara VPS; menus de chat; migração provider pool |
| `#9` `9b47339` | Gemini descontinuado; auto-config 9Router no deploy |
| `#10` `3b8a8fc` | Delete de chat com limpeza DB e erro visível na UI |

---

### OmniRoute automático — como funciona hoje

**Experiência do usuário**

- Em produção com `PKF_ROUTER_ONLY=1`, o usuário **não configura nem vê** provedores Groq/Gemini/Kimi no `.env` — o pool é só `ninerouter`.
- Mensagens de erro em `pkf/errors.py` usam texto genérico (“gateway de IA”, “limite momentâneo”) quando `router_only_mode()` ou `provider == "ninerouter"`, em vez de pedir chaves diretas.
- O deploy (`update.sh`) executa automaticamente `fix-ninerouter-key.sh` e `setup-omniroute-providers.sh`, que registra provedores free (`open-code`, `pollinations`, `cloudflare-ai`) via API interna do OmniRoute — **sem abrir o dashboard**.

**Lógica de fallback entre provedores**

1. **`router_only_mode()`** (`PKF_ROUTER_ONLY=1`): `provider_pool_names()` retorna `["ninerouter"]` — sem fallback para Groq/Gemini nativos.
2. **`default_provider()`**: prioridade — alias `PKF_PROVIDER=omniroute|9router` → `ninerouter`; se router-only e gateway habilitado → `ninerouter`; senão explícito → 9Router com skip proativo → Groq → Gemini → Kimi → OpenAI → DeepSeek → Ollama. O gate `PKF_ENV == "production"` **permanece removido** (fix da rodada 2); a novidade é a **prioridade do gateway** antes das chaves diretas.
3. **Rotação de modelos no 429**: `fallback_model_on_rate_limit()` usa `ninerouter_model_chain()` quando o client aponta para o gateway — cadeia padrão `auto/free,auto,auto/coding,oc/big-pickle` (override via `PKF_NINEROUTER_MODEL_CHAIN`); `NINEROUTER_MODEL` default em produção: `auto/free`.
4. **Rotação de provider**: `pkf/provider_errors.py` — `should_rotate_provider()` trata 429/5xx e, no `ninerouter`, também 401/403; em router-only não há segundo provedor no pool.
5. **Imagem Docker**: `ROUTER_IMAGE` default `diegosouzapw/omniroute:latest` (substitui `decolua/9router:latest`).

---

### Estabilidade de conexão — bugs corrigidos e causas

| Bug | Causa raiz (evidência no diff/commit) | Correção |
|-----|----------------------------------------|----------|
| **Tela branca** | `useRef(applySession)` avaliado **antes** de `applySession` existir → `ReferenceError` no bundle (`d4b2045`) | Refs inicializados vazios; `applySessionRef.current = applySession` **após** `useCallback` |
| **Loop de login / auth** | WS reconectava sem token válido; Bearer mal normalizado; modal não abria em falha provável (`6685f1a`, `00f00c0`) | `connect()` aborta se `authRequired && !getToken()`; boot HTTP completa `/api/session` antes de abrir WS; token persistido em `?token=` na URL |
| **WebSocket 1006 / reconexão infinita** | Cleanup do `useEffect` de boot fechava WS recém-aberto; race entre gerações de socket (`f147581`, `6703c98`) | Lifecycle WS **separado** do boot (`sessionReady`); `activeSocketIdRef` invalida handlers stale; close intencional com código 1000 |
| **"Servidor indisponível" com backend OK** | Handshake WS fechava antes de enviar erro legível; StrictMode duplicava efeitos (`main.tsx`) | Servidor aceita WS antes de checar auth (`server.py`); mensagem JSON no socket; **StrictMode removido** em `main.tsx` |
| **Chat sem tempo real no navegador** | WS falha intermitente (proxy/NAT) após 8 tentativas (`58849b5`, `8545263`) | Fallback **`POST /api/message`** compartilhando handler com WS; banner "Modo HTTP"; retry WS a cada 30s |

**Boot atual (`App.tsx`)** — sequência verificada no código:

1. `GET /api/health` → define `authRequired`.
2. Se auth obrigatório e sem token → modal, **sem** WS.
3. `GET /api/session` → `applySession`, `applyLibrary(data.library)`, marca `sessionBootstrappedRef`.
4. Sincroniza token na query string (`?token=`).
5. **`loadLibrary()`** sempre roda em seguida (mesmo após passo 3).
6. `setSessionReady(true)` → segundo `useEffect` abre WebSocket após 100ms.

---

### CI (`ci.yml`) vs deploy (`deploy.yml`)

| Workflow | Disparo | O que faz | Relação |
|----------|---------|-----------|---------|
| **`ci.yml`** (novo) | push e PR na `main` | Job `backend`: ruff + pytest; job `frontend`: `npm ci` + `npm run build`; jobs **paralelos**; concurrency cancela run anterior | **Verificação** — não deploya |
| **`deploy.yml`** (existente) | push na `main` | SSH → `git pull` + `update.sh`; health check opcional | **Deploy** — independente do CI |

O CI **não substitui** nenhuma etapa do deploy. Ambos podem rodar no mesmo push na `main` (CI valida, deploy publica). Correção em `e90e5f2`: expressão `if:` inválida com secrets no deploy (health check).

---

### Docker / infra — mudanças de ambiente

| Arquivo | Mudança |
|---------|---------|
| `docker-compose.yml` | `PKF_PROVIDER` default `ninerouter`; `PKF_ROUTER_ONLY` default `1`; `PKF_AUTH_TOKEN` exposto; imagem router `ROUTER_IMAGE` |
| `.env.example` | Documentação OmniRoute/router-only; `OPENAI_MODEL=gpt-4o-mini`; Headroom porta 8788 |
| `.env.production.example` | Modo router-only como **padrão**; chaves Groq/Gemini comentadas; `NINEROUTER_MODEL=auto/free` |

---

### Status dos itens da rodada anterior

| Item | Status | Evidência |
|------|--------|-----------|
| Menu ⋯ em Projetos (`Sidebar.tsx`) | **Válido** | Botões `⋯` com Fixar / Renomear / Excluir presentes (~L139–191); bulk delete adicionado depois |
| Fix flicker sidebar no boot (`App.tsx`) | **Alterado** | Rodada 2: boot **não** chamava `applyLibrary` de `/api/session`. **Hoje** linha ~265 chama `applyLibrary(data.library)` **e** `loadLibrary()` — fix original **sobreposto** pela leva WebSocket |
| Fix modelo `gpt-5.4-mini` | **Alterado** | `f998b20` definiu `gpt-5.4-mini`; `cd82093` corrigiu (“não existe”); **default atual** em `pkf/config.py`: **`gpt-4o-mini`**; `set-env-keys.sh` migra `gpt-5.4-mini` → `gpt-4o-mini` |
| `default_provider()` sem gate `PKF_ENV` | **Válido (lógica base) + expandido** | Gate `PKF_ENV == "production"` **continua ausente**; adicionadas prioridades `router_only_mode()`, alias `omniroute`, e skip proativo 9Router |

---

### Definition of Done (auditoria)

- [x] Todos os commits da leva listados e agrupados por tema
- [x] Cada tema com explicação causa/efeito (não só lista de arquivos)
- [x] Status de cada item da rodada anterior confirmado (válido / alterado / não determinado)
- [x] Nenhum arquivo de código alterado nesta tarefa — **somente** `CHANGELOG_MELHORIAS.md`

### Testes (revalidação Fase 4)

```
175 passed in 5.30s
```

Comando: `python3 -m pytest tests/ -q`

---

## CI/CD — Deploy automático via GitHub Actions

**Data:** 2026-08-17

### Implementado

- **`.github/workflows/deploy.yml`**: dispara em push na `main`; SSH via `appleboy/ssh-action@v1.2.0`; executa `git pull` + `deploy/hostinger/update.sh` na VPS; timeout 10 min; health check opcional com 3 tentativas (`VPS_HEALTHCHECK_URL`).
- **`PKF.md`**: seção "Deploy automático" com lista de Secrets e recomendação de chave SSH dedicada.
- **`tests/test_deploy_workflow.py`**: validação estrutural + `yaml.safe_load()` quando PyYAML disponível.

### Manual (fora do Cursor)

- Cadastrar Secrets no GitHub: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_PORT` (opcional), `VPS_HEALTHCHECK_URL` (opcional).
- Gerar chave SSH dedicada na VPS (recomendado).

### Merge `fix/pendencias-rodada2`

- Integrado na `main` via PR #1 (`5639840`).

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
| Chamada real via proxy Headroom | **não medida** — Headroom não estava rodando neste ambiente; medir manualmente após `headroom proxy --port 8788` |

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
