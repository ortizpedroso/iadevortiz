# Spec — Correções UI e validação de spec

**Data:** 2026-08-22  
**Branch:** `cursor/pkf-ui-and-spec-fixes-1cb2`  
**Base:** `main`

## Objetivo

Corrigir quatro problemas confirmados em produção/uso real, sem escopo extra.

---

## Tarefa 1 — Contraste do painel de spec

**Causa raiz:** `SpecPanel.tsx` linha ~53 usa `text-[#cfcfcf]` hardcoded (tema escuro), ilegível no tema claro.

**DoD:** Texto do corpo da spec usa `text-[var(--pkf-text)]`; nenhuma cor hardcoded de tema antigo no painel.

**Resultado:** `text-[#cfcfcf]` → `text-[var(--pkf-text)]` no container do corpo da spec.

**Verificação:** Inspeção visual do componente — cor agora segue token do tema claro.

---

## Tarefa 2 — Sidebar de projetos some sozinha

**Causa raiz:** `App.tsx` forçava `setPanel("spec")` em todo `applySession` com spec `pending_approval`.

**DoD:** Spec pendente abre automaticamente só na primeira vez; usuário pode voltar ao painel de projetos; botões Projetos/Spec sempre visíveis.

**Resultado:**
- `specAutoShownRef` + `userChoseProjectPanelRef` controlam auto-abertura
- `maybeOpenSpecPanel` só força spec na 1ª vez (ou evento WS `spec_preview` novo)
- Botões **Projetos** e **Spec** no header (mobile + desktop), com estado ativo visual
- Hamburger mobile marca `userChoseProjectPanelRef` ao abrir projetos

**Verificação:** Revisão de fluxo em `App.tsx` — `applySession` não re-força spec se usuário já escolheu projetos.

---

## Tarefa 3 — Menu de chat sem renomear

**Causa raiz:** Chats sem Renomear; sem `PATCH /api/chats/{id}`.

**DoD:** Renomear chat inline; menu visual alinhado ao de projetos; endpoint PATCH.

**Resultado:**
- `PATCH /api/chats/{chat_id}` com `{ title }`
- `rename_chat` em `library.py` — atualiza `index.json` (file mode) e `custom_titles.json` (override para DB mode)
- `ChatRow` com edição inline + item Renomear; menu usa `bg-[var(--pkf-bg-elevated)]` como projetos
- `onRenameChat` em `App.tsx` → `fetch PATCH`

**Verificação:** `tests/test_rename_chat.py::test_rename_chat_updates_title_in_file_mode`

---

## Tarefa 4 — `save_spec` aceita conteúdo vazio de substância

**Causa raiz:** `save_spec` só rejeitava `content.strip()` vazio.

**DoD:** Rejeitar spec mínima tipo "Especificação da landing page."; specs substanciais passam.

**Resultado:** `validate_spec_substance` em `pkf/spec/document.py` — corpo ≥ 300 chars OU ≥ 2 seções com ≥ 40 chars cada.

**Verificação:**
- `tests/test_save_spec_validation.py::test_save_spec_rejects_minimal_landing_page`
- `tests/test_save_spec_validation.py::test_save_spec_accepts_valid_title_and_stack` (corpo expandido)

---

## Testes

`python3 -m pytest tests/ -q` → **253 passed**
