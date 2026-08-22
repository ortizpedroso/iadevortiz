# Auditoria profunda — Grafos, agentes, memória, coerência e anti-alucinação

**Data:** 2026-08-22  
**Branch:** `cursor/pkf-deep-audit`  
**Escopo:** Somente investigação — **nenhum código em `pkf/` ou `frontend/src/` foi alterado.**  
**Baseline:** `python3 -m pytest tests/ -q` → **251 passed** (antes e depois desta auditoria).

**Metodologia:** Leitura completa dos módulos listados no prompt + testes empíricos ad-hoc (scripts Python executados no ambiente de auditoria, não commitados). Leitura isolada sem teste empírico é indicada explicitamente.

**Código auditado:** `main` no momento da auditoria (inclui Grupo D `state_events` — PR #27 de remoção ainda não mergeado).

---

## Resumo executivo

| Severidade | Quantidade |
|------------|------------|
| Crítica | 0 |
| Alta | 3 |
| Média | 6 |
| Baixa | 4 |
| Informativo | 7 |

**Veredicto:** O sistema **entrega parcialmente** o que promete. O DAG executa em paralelo de fato e o handoff é injetado no payload do agente dependente, mas **falhas em tarefas upstream não bloqueiam downstream** (tarefa com erro ainda entra em `completed`), o que pode gerar implementação sobre base incompleta. Mecanismos anti-alucinação legados (`save_spec`, memória com threshold, `get_last_verification`, prompts de verificação de workspace) **permanecem ativos e testados**, porém **handoff e compactação LLM introduzem um ponto cego novo**: resumos auto-gerados propagados como fato sem cruzamento com `file_changes` ou leitura de disco.

---

## Itens já conhecidos (severidade reavaliada)

| Item pendente | Severidade | Impacto |
|---------------|------------|---------|
| Consulta barata do agente à resposta completa de fase anterior | **Média** | Agentes dependentes só recebem handoff truncado (2000 chars), não a resposta integral — perda de detalhe em builds complexos. |
| Fase 0 de scaffolding em paralelo | **Informativo** | Não existe; `TaskTree.tsx` não reflete algo que o backend não implementa. |
| Memória lazy + limite máximo de entradas | **Alta** (escala) | `_restore_memory_agents()` cria um agente por entrada no boot; sem teto, degrada startup e RAM em workspaces longos. |
| Detecção de arquivos/pastas obsoletos pós-build | **Média** | Lixo acumula no workspace; reviewer pode focar em arquivos mortos. |
| `TaskTree.tsx` sem Fase 0/handoff/obsoletos | **Baixa** | UX incompleta, não quebra pipeline. |

---

## Achados detalhados

| ID | Severidade | Categoria | Local | Achado | Evidência | Recomendação |
|----|------------|-----------|-------|--------|-----------|--------------|
| **AUD-001** | **Alta** | DAG / Orquestração | `pkf/workflow/orchestrator.py` (`run_build_dag`, linhas 155–166) | Tarefas que retornam `Erro: …` são adicionadas a `completed` igual a sucessos. Dependentes (`frontend` após `backend` falho) **ainda executam**. | Script empírico: `backend` lançou `RuntimeError`, `logic` concluiu, `frontend` rodou com payload contendo handoff só de `logic`. Resultado: `[('backend','Erro:…'), ('logic','logic done'), ('frontend','fe done')]`, `frontend_ran_after_backend_fail=True`. | Só marcar `completed` em sucesso; ou propagar status `failed` e bloquear dependentes; ou exigir handoff obrigatório das deps antes de rodar. |
| **AUD-002** | **Alta** | Handoff / Anti-alucinação | `pkf/workflow/orchestrator.py` + `pkf/workflow/handoff.py` | Handoff grava a **resposta textual do LLM** (`reply[:2000]`) sem cruzar com `file_changes`, `list_changes` ou leitura de arquivos. Agente pode exagerar o que fez; dependente recebe isso como “Contexto de handoff (dependências concluídas)”. | `save_handoff` chamado com `summary=(reply or …)[:2000]`; parâmetro `artifacts` **nunca** passado no orquestrador. Nenhuma função compara resumo vs. disco. | Preencher `artifacts` a partir de `file_changes` da sessão; prefixar handoff com lista verificada de paths; ou exigir `read_file` na tarefa dependente antes de codificar. |
| **AUD-003** | **Alta** | Memória / Escala | `pkf/router.py` (`_restore_memory_agents`) | Boot cria **todos** os agentes de memória de uma vez, sem lazy loading nem teto. | Com 100 entradas sintéticas em `index.json`: `restore_time=0.017s`, `mem_agents=100` objetos `Agent` instanciados. Crescimento linear sem limite documentado. | Lazy: criar agente só no `find()` acima do threshold; cap configurável (ex. 20); LRU ou TTL no índice. |
| **AUD-004** | **Média** | DAG / UX de erro | `pkf/workflow/task_graph.py` vs `orchestrator.py` | Detecção de ciclo: `topological_layers` levanta `ValueError("Ciclo detectado…")`, mas `run_build_dag` (caminho real) levanta `RuntimeError("Deadlock no DAG…")`. Router não captura. | Ciclo A↔B: `topo_err="Ciclo detectado no DAG de tarefas"`; `run_build_dag` → `('RuntimeError', 'Deadlock no DAG: dependências não satisfeitas para a')`. `grep` em `router.py`: sem `try/except` em torno de `run_build_dag`. | Unificar mensagem; validar DAG no planner antes do build; traduzir para resposta amigável na UI. |
| **AUD-005** | **Média** | Handoff | `pkf/workflow/handoff.py` | `MAX_SUMMARY=2000` **funciona** (truncamento real). | Input 5000 chars → `stored_len=2000`. | Manter; documentar que detalhes além de 2000 chars são perdidos (reforça AUD-001/AUD-002). |
| **AUD-006** | **Média** | Handoff / Propagação | `pkf/workflow/orchestrator.py` | Falha em agente **não** grava handoff (`save_handoff` só no `try` de sucesso), mas `task_id` falho ainda libera dependentes (ver AUD-001). | Após falha de `backend`: `handoffs_after_fail=['logic','frontend']` — sem chave `backend`. `frontend` executou mesmo assim. | Combinar com fix de AUD-001; opcionalmente gravar handoff de falha com flag `status: failed`. |
| **AUD-007** | **Média** | Compactação / Anti-alucinação | `pkf/agents/compact.py` | Resumo estruturado LLM (mesmo risco de AUD-002): template forçado via `_ensure_template_sections`, mas **conteúdo não é verificado** contra workspace. | `test_compact_llm.py` (mock) confirma template e combinação com resumo anterior — **não** valida verdade factual. Leitura de `compact_messages_llm`: sem pós-validação. | Injetar lista de arquivos tocados na sessão no prompt de compactação; ou marcar seções como “não verificado”. |
| **AUD-008** | **Média** | Memória / Estado | `pkf/memory/store.py` | `index.json` só cresce (`register` → `save`); sem eviction. | Código: `register` append-only; teste empírico 100 entradas sem remoção. | Limite + política de arquivo ou merge de entradas antigas. |
| **AUD-009** | **Baixa** | DAG | `pkf/workflow/planner.py` | Spec parcial (só `backend`+`frontend`) gera DAG correto sem tarefas vazias. | `agents=['backend','frontend']`, `deps={'backend':[], 'frontend':['backend']}`, `layers=[['backend'],['frontend']]`. | Nenhuma ação urgente; comportamento saudável. |
| **AUD-010** | **Baixa** | DAG / Paralelismo | `pkf/workflow/orchestrator.py` | Paralelismo no mesmo nível do DAG **confirmado empiricamente**. | `backend`+`logic` na mesma camada: offsets de início `[0.0, 0.0002]` s com `sleep(0.3)` — inícios simultâneos. | Manter; adicionar teste permanente de timing se regressão for preocupação. |
| **AUD-011** | **Baixa** | Handoff / Isolamento | `pkf/workflow/handoff.py` | Handoffs isolados por workspace (`.pkf/session_handoffs.json` por `workspace.root`). | Projeto A `PROJECT_A_SECRET` não apareceu no contexto do projeto B. | OK; manter paths relativos ao workspace. |
| **AUD-012** | **Baixa** | Handoff / Injeção | `pkf/workflow/orchestrator.py` | `handoff_context_for_deps` **é injetado** em `agent.process(payload)` na linha 87–90. | Build encadeado: `frontend_payload_has_handoff_section=True`, `HANDOFF_REPLY` presente no payload. | OK; coberto por `tests/test_graph_orchestration.py` parcialmente. |
| **AUD-013** | **Informativo** | Anti-alucinação (regressão) | `pkf/router.py`, `pkf/agents/prompts.py` | Agente de memória mantém ferramentas `project_context`, `list_dir`, `read_file`, `search_code` e prompt exigindo verificar workspace. | `tests/test_memory.py::test_memory_agent_has_read_tools_and_workspace_check_prompt` **passed**; releitura de `_restore_memory_agents` confirma texto “conversa ANTERIOR” e “list_dir”. | Nenhuma regressão detectada. |
| **AUD-014** | **Informativo** | Anti-alucinação (regressão) | `pkf/tools/impl.py` (`save_spec`) | Validação de título longo e `suggested_stack` malformado **ativa**. | `tests/test_save_spec_validation.py` — 3 testes **passed** (rejeita frase longa, lista de rótulos; aceita válido). | Nenhuma regressão. |
| **AUD-015** | **Informativo** | Verificação T3 | `pkf/verify_store.py`, `pkf/tools/impl.py` | Persistência e leitura de verificação real funcionam. | `save_last_verification` → `load_last_verification` ok=False; `get_last_verification(ws)` contém `"pytest failed: 3 errors"`. Prompt `generalista` em `prompts.py` ainda exige `get_last_verification` antes de hipóteses T3 (leitura estática). | Nenhuma regressão; enforcement depende do LLM seguir prompt. |
| **AUD-016** | **Informativo** | Continuidade de chat | `pkf/router.py` (`restore_chat_history`) | Fix D2 mantido: só agente ativo recebe histórico. | `tests/test_security_remediation.py::test_restore_chat_history_only_active_agent` **passed** — architect com 1 user msg, generalista com 0. | Nenhuma regressão. |
| **AUD-017** | **Informativo** | Compactação | `pkf/agents/compact.py` | Template estruturado e combinação com resumo anterior **testados** (mocks). | `tests/test_compact_llm.py` — 5 testes **passed**; mecânico reduz 31→10 msgs. | Falta teste e2e com LLM real (aceitável). |
| **AUD-018** | **Informativo** | Memória / Falso positivo | `pkf/memory/store.py` | Threshold 45% + min 3 termos evita match genérico “cardápio digital”. | `tests/test_memory.py` — `test_memory_ignores_generic_domain_words`, `test_memory_does_not_match_similar_projects_with_shallow_overlap` **passed**. | Calibração atual adequada para casos conhecidos. |
| **AUD-019** | **Informativo** | Pub/Sub (legado) | `pkf/workflow/orchestrator.py` | `_notify_agent_done` ainda importa `pkf.web.state_events` em `main` (PR #27 aberto para remoção). | `grep state_events orchestrator.py` → True. Não testado em runtime com DB nesta auditoria. | Merge PR #27 ou documentar dependência até lá. |

---

## Detalhamento por grupo (testes empíricos)

### Grupo 1 — DAG e orquestração

| Teste | Resultado |
|-------|-----------|
| **1.1** Spec só backend+frontend | **OK** — sem logic/tester; `frontend.depends_on=['backend']` apenas. |
| **1.2** Paralelismo real | **OK** — `asyncio.gather` dispara mesmo nível com inícios simultâneos (offsets &lt; 1ms). |
| **1.3** Falha na mesma camada | **FALHA de design** — `logic` continua; `frontend` roda após `backend` falhar → **AUD-001**, **AUD-006**. |
| **1.4** Ciclo no DAG | **Parcial** — `ValueError` em `topological_layers`; `run_build_dag` → `RuntimeError` “Deadlock” → **AUD-004**. |

### Grupo 2 — Handoff

| Teste | Resultado |
|-------|-----------|
| **2.1** Truncamento 2000 | **OK** → AUD-005. |
| **2.2** Injeção no payload | **OK** → AUD-012. |
| **2.3** Isolamento workspace | **OK** → AUD-011. |

### Grupo 3 — Anti-alucinação

| Teste | Resultado |
|-------|-----------|
| **3.1** Memória + ferramentas | **OK** → AUD-013. |
| **3.2** `save_spec` | **OK** → AUD-014. |
| **3.3** `verify_store` | **OK** → AUD-015. |
| **3.4** Risco novo handoff/compact | **Achado** → AUD-002, AUD-007. |

### Grupo 4 — Continuidade

| Teste | Resultado |
|-------|-----------|
| **4.1** `restore_chat_history` | **OK** → AUD-016. |
| **4.2** Compactação | **OK** (mocks + mecânico) → AUD-017. |
| **4.3** Memória cardápio | **OK** → AUD-018. |

### Grupo 5 — Memória / crescimento

| Teste | Resultado |
|-------|-----------|
| **5.1** Entradas + tempo boot | 0 entradas no repo; sintético 100 → 0.017s, 100 agentes → **AUD-003**. |
| **5.2** Outros estados sem limite | `memory.index` (AUD-008); `session_handoffs.json` por task_id (bounded por build); `agent.messages` até compactação; `file_changes` no DB (sem purge automática — **Baixa**, não quantificado). |

---

## Scripts de teste (descartáveis)

Os testes empíricos foram executados via script Python inline no shell da auditoria (**não commitados**). Para reproduzir os cenários 1.1–1.4 e 2.x, reexecutar lógica equivalente a `tests/test_graph_orchestration.py` + mocks de `run_build_dag` conforme evidências acima.

Testes **permanentes** relevantes já no repositório:

- `tests/test_graph_orchestration.py` — DAG, ordem de deps, `ast_parser`
- `tests/test_memory.py` — anti-falso-positivo cardápio
- `tests/test_save_spec_validation.py` — validação spec
- `tests/test_compact_llm.py` — compactação estruturada
- `tests/test_security_remediation.py` — `restore_chat_history` só agente ativo

---

## Definition of Done (auditoria)

- [x] Leitura obrigatória dos módulos listados
- [x] `pytest tests/ -q` → 251 passed
- [x] Testes empíricos Grupos 1–5 executados
- [x] Nenhuma alteração em `pkf/` ou `frontend/src/`
- [x] Relatório com severidade, evidência e recomendação
- [x] `git diff --stat main` mostra apenas `docs/AUDITORIA_AGENTES.md`

---

## Próximos passos sugeridos (fora deste escopo)

1. Corrigir **AUD-001** antes de confiar no DAG em produção com specs complexas.
2. Endurecer handoff (**AUD-002**) com artefatos verificados.
3. Merge ou rejeição explícita do pub/sub (**AUD-019** / PR #27).
4. Prompt separado de remediação para memória lazy (**AUD-003**).
