# Spec — Fechar lacunas restantes (continuidade, consulta, Média, UI)

**Data:** 2026-08-22  
**Branch:** `cursor/pkf-close-remaining-gaps-1cb2`  
**Base:** `cursor/pkf-audit-remediation` (PR #29, não mergeado)

## Objetivo

Implementar exclusivamente 4 tarefas pendentes após a remediação da auditoria.

---

## Achados Média (6 itens)

| ID | Achado | Status neste PR |
|----|--------|-----------------|
| **AUD-004** | Ciclo DAG: mensagem unificada `DagValidationError` | Corrigido (herdado de `pkf-audit-remediation`) — teste mantido |
| **AUD-005** | `MAX_SUMMARY=2000` documentado + truncamento real | Corrigido — `test_handoff_truncates_at_max_summary` |
| **AUD-006** | Handoff de falha + bloqueio de dependentes | Corrigido (herdado) — teste mantido |
| **AUD-007** | Compactação LLM com paths verificados | Corrigido (herdado) — teste mantido |
| **AUD-008** | Limite do índice de memória | Corrigido (herdado) — teste mantido |
| **Consulta barata** | Resposta completa de fase anterior sem reinvocar agente | **Novo** — `get_prior_phase_response` + `build_agent_responses.json` |

---

## Tarefa 1 — Handoff + retomada de build

**Requisito:** Ao retomar (`/build resume`), o orquestrador reutiliza handoffs persistidos em `.pkf/session_handoffs.json` via `handoff_context_for_deps`. Checkpoint documenta handoffs disponíveis. Árvore marca agentes retomados.

**DoD:**
- [x] `resume_handoff_summary` gravado no checkpoint
- [x] `tracker.mark_resume_agents` com detail "retomado — handoff preservado"
- [x] `tests/test_close_remaining_gaps.py::test_resume_build_injects_persisted_handoffs`

---

## Tarefa 2 — Consulta barata à resposta completa

**Requisito:** Ferramenta `get_prior_phase_response` lê `.pkf/build_agent_responses.json` (limite `PKF_BUILD_RESPONSE_MAX_ENTRIES=20`, `PKF_BUILD_RESPONSE_MAX_CHARS=50000`). Orquestrador grava resposta integral após cada tarefa. Disponível para `frontend`, `logic`, `tester`.

**DoD:**
- [x] `pkf/workflow/build_results.py`
- [x] `tests/test_close_remaining_gaps.py::test_get_prior_phase_response_returns_full_not_handoff_truncated`
- [x] `tests/test_close_remaining_gaps.py::test_build_results_enforces_max_entries`

---

## Tarefa 3 — Achados Média

**DoD:** Todos os 6 itens acima com teste ou documentação de pendência. Nenhuma pendência de arquitetura grande.

---

## Tarefa 4 — TaskTree.tsx

**Requisito:** Exibir `detail` (handoff, pulado, retomado) e status `skipped`. Backend emite via `TaskNode.detail` e `status=skipped`.

**DoD:**
- [x] `frontend/src/types.ts` — campo `detail`
- [x] `frontend/src/components/TaskTree.tsx` — ícones/cores para skipped + detail
- [x] `tests/test_close_remaining_gaps.py::test_skipped_tasks_mark_tracker_status`
- [x] `tests/test_close_remaining_gaps.py::test_mark_resume_agents_sets_detail`

---

## Fora de escopo

- Validação e2e com LLM real em produção
- Novos mecanismos assíncronos (pub/sub)
