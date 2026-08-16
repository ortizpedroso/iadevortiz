# PKF — IA de Desenvolvimento

Assistente multiagente para especificar, implementar, revisar e testar código no seu workspace.

## O que ela faz

- Pipeline **compose**: brainstorm → build paralelo → verify → juiz → review
- **Memória persistente** (`MEMORY.md`, `checkpoint.md`) entre sessões
- **Skills BM25** — carrega automaticamente frontend-design, python-toolchain, cardápio, etc.
- **Árvore de tarefas** na sidebar (T1 spec → T2 build → T3 verify → T4 review)
- **`/goal`** — define meta; juiz independente valida se foi atingida
- Pool de provedores com rotação (Groq, Gemini, **MiMo**, Kimi)
- Compactação de contexto **por modelo**
- UI web com preview embutido

## Como usar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m pkf --ui
```

Provedores (`.env`):

```env
PKF_PROVIDER_POOL=groq,gemini,mimo
GROQ_API_KEY=...
GEMINI_API_KEY=...
MIMO_API_KEY=...
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
PKF_JUDGE_MODEL=llama-3.1-8b-instant
```

## Comandos

| Comando | Função |
|---|---|
| `/spec [nome]` | Gera spec automática |
| `/build [nome]` | Pipeline compose completo |
| `/review` | Compara código e spec |
| `/goal [meta]` | Condição de parada do build |
| `/status` | Fase, spec, meta e agente |

Deploy VPS: [DEPLOY.md](DEPLOY.md)

## Segurança

Ferramentas presas ao workspace. `.env` e chaves bloqueados. Terminal com allowlist.
