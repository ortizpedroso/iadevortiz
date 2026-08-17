# Changelog — Melhorias PKF (Fases 1–4)

Resumo das melhorias de confiabilidade, segurança e busca implementadas no repositório PKF.

## Fase 1 — Confiabilidade do `edit_file`

**Implementado:**
- Detecção de trecho ambíguo (`old_string` duplicado sem `replace_all`)
- Erro quando `old_string == new_string`
- Validação de sintaxe pós-escrita (`.py` via `ast.parse`, `.json` via `json.loads`) com reversão automática
- Auditoria com `old`/`new` + `unified_diff` truncado no log de mudanças

**Arquivos:** `pkf/tools/impl.py`, `tests/test_tools_edit.py`, ajuste mínimo em `tests/test_improvements.py`

**Testes novos:** 7 (`test_tools_edit.py`)

---

## Fase 2 — Lock de escrita entre agentes paralelos

**Implementado:**
- Lock por arquivo (`asyncio.Lock`) em `Workspace.file_lock()`
- `ToolRegistry.execute_async()` adquire lock antes de `write_file`/`edit_file`
- Evento `tool` com `info=aguardando lock em <arquivo>` quando lock ocupado
- Agentes usam `await tools.execute_async()` em `pkf/agents/base.py`

**Arquivos:** `pkf/workspace.py`, `pkf/tools/registry.py`, `pkf/agents/base.py`, `pkf/router.py`, `tests/test_tools_lock.py`

**Testes novos:** 2 (`test_tools_lock.py`)

---

## Fase 3 — Sandbox para `run_command`

**Implementado:**
- Parse com `shlex.split()`; primeiro token validado contra allowlist
- Rejeição de encadeamento (`&&`, `;`, `|`, `` ` ``, `$(`, `>`, `<`)
- `subprocess.run(..., shell=False, cwd=workspace.root)`
- Ambiente filtrado (remove `*_API_KEY`, `*_TOKEN`, `*_SECRET`, `DATABASE_URL`)
- Timeout via `COMMAND_TIMEOUT`; saída truncada em ~10 KB
- Docstring atualizada em `TOOL_DEFINITIONS["run_command"]`

**Arquivos:** `pkf/tools/impl.py`, `pkf/tools/registry.py`, `tests/test_run_command.py`

**Testes novos:** 6 (`test_run_command.py`)

---

## Fase 4 — Indexação semântica de código

**Implementado:**
- Módulo `pkf/semantic_index.py` com embeddings locais (`sentence-transformers/all-MiniLM-L6-v2`)
- Fallback de teste leve via `PKF_TEST_SEMANTIC=1` (sem carregar modelo pesado)
- Chunks por função/classe (`.py`) ou blocos de ~80 linhas
- Índice em `.pkf/index/semantic.json`
- Reindexação incremental em `write_file`/`edit_file` (`update_file_index`)
- `search_code` estendido com parâmetro `mode: "text" | "semantic"`
- Busca textual/BM25 existente preservada (`mode=text` padrão)

**Arquivos:** `pkf/semantic_index.py`, `pkf/tools/impl.py`, `pkf/tools/registry.py`, `requirements.txt`, `tests/test_semantic_index.py`

**Testes novos:** 4 (`test_semantic_index.py`)

---

## Resultados de teste

| Métrica | Valor |
|---------|-------|
| Testes antes (Fase 1 baseline) | 76 |
| Testes novos (Fases 1–4) | +19 |
| Total | **95** |

Rodar: `pytest tests/ -v`

---

## Próximos passos recomendados (não implementados)

1. **Sandbox Docker efêmero para `run_command`** — isolar subprocess em container descartável por execução (Fase 3 registrou como melhoria futura).
2. **Harness de benchmark interno** — rodar N specs de referência e medir taxa de sucesso de `/build` (meta, review aprovado, preview OK).
3. **Streaming de diffs granulares na UI** — mostrar mudanças linha a linha em tempo real durante o build, não só status de tarefa.
