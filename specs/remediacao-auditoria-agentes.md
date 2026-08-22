# Spec — Remediação da auditoria de agentes

**Data:** 2026-08-22  
**Branch:** `cursor/pkf-audit-remediation`  
**Fonte:** `docs/AUDITORIA_AGENTES.md` (PR #28)

## Objetivo

Corrigir achados de severidade **Alta** e **Média** da auditoria de agentes, preservando comportamentos já validados: DAG parcial, paralelismo real na mesma camada, isolamento de handoff por workspace, truncamento `MAX_SUMMARY=2000`.

## Não-requisitos (fora de escopo)

- Consulta barata à resposta completa de fase anterior
- Fase 0 de scaffolding em paralelo
- Detecção de arquivos/pastas obsoletos pós-build
- Extensão do `TaskTree.tsx`
- Achados Baixa/Informativo (exceto AUD-005 documentação trivial)

---

## Definition of Done

### AUD-001 (Alta) — DAG não executa dependentes após falha upstream

**Requisito:** Em `run_build_dag`, tarefas com resultado `Erro:` entram em conjunto `failed`, não em `succeeded`. Dependentes diretos e transitivos são marcados `skipped` com mensagem legível (`Pulado: dependência 'X' falhou.`). Tarefas independentes na mesma camada (ex.: `logic` quando `backend` falha) podem continuar.

**Critério verificável:** `tests/test_audit_remediation.py::test_dag_blocks_frontend_when_backend_fails` — `frontend.process` não é chamado; resultado contém mensagem de skip.

---

### AUD-002 (Alta) — Handoff com artifacts verificáveis

**Requisito:** Ao concluir tarefa com sucesso, `save_handoff` recebe `artifacts` com paths reais de `list_changes` / `record_change` (via `changes.json`) desde o início da tarefa. Handoff injetado lista artefatos verificados.

**Critério verificável:** `tests/test_audit_remediation.py::test_handoff_artifacts_from_recorded_changes` — após `write_file` + build mock, `artifacts` não vazio.

---

### AUD-003 (Alta) — Memória lazy + limite de entradas

**Requisito:** (a) Remover criação eager de agentes em `_restore_memory_agents` no boot; criar via `_ensure_memory_agent` só quando `memory.find` retorna match. (b) `MemoryStore.register` respeita `PKF_MEMORY_MAX_ENTRIES` (padrão 50), evict FIFO da entrada mais antiga.

**Critério verificável:**
- `tests/test_audit_remediation.py::test_router_boot_does_not_create_all_memory_agents`
- `tests/test_audit_remediation.py::test_memory_store_enforces_max_entries`

---

### AUD-004 (Média) — Erro de ciclo DAG compreensível

**Requisito:** Validar DAG no início de `run_build_dag` com `topological_layers`; levantar `DagValidationError` com mensagem unificada. Router captura e retorna texto amigável ao usuário (não stack trace cru).

**Critério verificável:** `tests/test_audit_remediation.py::test_dag_cycle_raises_validation_error` + `test_router_build_handles_dag_cycle` (ou equivalente).

---

### AUD-005 (Média) — Documentar truncamento de handoff

**Requisito:** Documentar em `handoff.py` que resumos >2000 chars são truncados e detalhes extras são perdidos.

**Critério verificável:** docstring presente + teste existente de truncamento continua passando.

---

### AUD-006 (Média) — Handoff de falha + bloqueio de dependentes

**Requisito:** Em falha, gravar handoff com `status: failed` e resumo do erro. `handoff_context_for_deps` não inclui entradas `failed`. Bloqueio de dependentes coberto por AUD-001.

**Critério verificável:** `tests/test_audit_remediation.py::test_failed_handoff_not_injected_to_dependents`

---

### AUD-007 (Média) — Compactação LLM com contexto de arquivos verificados

**Requisito:** `compact_messages_llm` recebe `workspace_root` opcional; quando presente, injeta lista de paths de `list_changes` no prompt com rótulo “verificados no workspace”.

**Critério verificável:** `tests/test_audit_remediation.py::test_compact_llm_includes_recent_file_changes`

---

### AUD-008 (Média) — Limite do índice de memória

**Requisito:** Mesmo mecanismo de AUD-003 (`PKF_MEMORY_MAX_ENTRIES` + eviction FIFO em `register`).

**Critério verificável:** `test_memory_store_enforces_max_entries` (compartilhado com AUD-003).

**Justificativa de não duplicar:** AUD-008 e AUD-003 são resolvidos pelo mesmo código.

---

## Ordem de implementação

1. AUD-001  
2. AUD-002  
3. AUD-003 (+ AUD-008)  
4. AUD-004, AUD-005, AUD-006, AUD-007 (Média)

## Status da implementação (review 2026-08-22)

- [x] AUD-001 — `tests/test_audit_remediation.py::test_dag_blocks_frontend_when_backend_fails`
- [x] AUD-002 — `tests/test_audit_remediation.py::test_handoff_artifacts_from_recorded_changes`
- [x] AUD-003 — `tests/test_audit_remediation.py::test_router_boot_does_not_create_all_memory_agents`
- [x] AUD-004 — `tests/test_audit_remediation.py::test_dag_cycle_raises_validation_error`
- [x] AUD-005 — docstring `MAX_SUMMARY` em `handoff.py`
- [x] AUD-006 — `tests/test_audit_remediation.py::test_failed_handoff_not_injected_to_dependents`
- [x] AUD-007 — `tests/test_audit_remediation.py::test_compact_llm_includes_recent_file_changes`
- [x] AUD-008 — `tests/test_audit_remediation.py::test_memory_store_enforces_max_entries`
- [x] `tests/test_platform_build_review_cycle.py` — APROVADO
