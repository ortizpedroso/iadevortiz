# PKF — IA de Desenvolvimento

Assistente multiagente para especificar, implementar, revisar e testar código.

## Stack da plataforma

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, WebSocket |
| Frontend | Vite, React 19, TypeScript, Tailwind CSS 4 |
| Banco | PostgreSQL 16 (SQLAlchemy async + Alembic) |
| IA | OpenAI SDK — router nativo (tiers, multi-chave, Groq, Gemini, Kimi, DeepSeek-R1) |
| Deploy | Docker Compose, Nginx, volume workspace |

## Desenvolvimento local

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

# PostgreSQL (Docker)
docker compose up -d postgres

# Frontend (terminal separado)
cd frontend && npm install && npm run dev

# API + UI legacy ou dist
set DATABASE_URL=postgresql+asyncpg://pkf:pkf@localhost:5432/pkf
python -m pkf --ui
```

Build frontend para produção:

```bash
cd frontend && npm run build
python -m pkf --ui
```

## Deploy VPS

```bash
cd /opt/pkf && git pull && docker compose build pkf && docker compose up -d
```

Inclui PostgreSQL, PKF (`:8765`) e Nginx opcional (`:8080` — evita conflito com Caddy na :80).

## Comandos

| Comando | Função |
|---|---|
| `/spec` | Gera spec automática |
| `/build` | Pipeline compose completo |
| `/review` | Revisa código vs spec |
| `/goal` | Meta de parada do build |

Deploy: [DEPLOY.md](DEPLOY.md)

## Router híbrido (recomendado para uso contínuo)

**9Router primário** (OpenCode Free, Kiro, multi-conta) + **router nativo fallback** (suas chaves diretas).

```bash
# VPS — subir PKF + 9Router
docker compose --profile router up -d
```

`.env` na VPS:

```env
NINEROUTER_URL=http://ninerouter:20128
PKF_PROVIDER=ninerouter
NINEROUTER_KEY=local
NINEROUTER_MODEL=oc/big-pickle
PKF_PROVIDER_TIERS=subscription,cheap,free
PKF_TIER_CHEAP=groq,gemini
GROQ_API_KEY=...              # fallback direto
GEMINI_API_KEY=...
```

No dashboard do 9Router (`http://127.0.0.1:20128`): conecte **OpenCode Free** e/ou **Kiro OAuth**, crie combo free.

## Router nativo (sem 9Router)

```env
PKF_PROVIDER_TIERS=subscription,cheap,free
PKF_TIER_SUBSCRIPTION=groq
PKF_TIER_CHEAP=gemini
PKF_TIER_FREE=groq
GROQ_API_KEY=...
GROQ_API_KEY_2=...          # rotação multi-conta
TAVILY_API_KEY=...          # web_search (se sem 9Router)
```

Fallback automático: tier → multi-chave → cooldown com `retry-after`.

## DeepSeek-R1 (reasoning)

Repositório oficial: [deepseek-ai/DeepSeek-R1](https://github.com/deepseek-ai/DeepSeek-R1) — documentação do modelo + pesos HF; **não** é agente CLI. A PKF integra via API (`deepseek-reasoner`).

```env
DEEPSEEK_API_KEY=sk-...
PKF_PROVIDER=deepseek                    # ou híbrido com 9Router + fallback
DEEPSEEK_REASONER_MODEL=deepseek-reasoner
PKF_REASONING_AGENTS=architect,reviewer,logic
PKF_REASONING_TEMPERATURE=0.6
PKF_WEB_SEARCH_FORMAT=deepseek           # citações estilo chat.deepseek.com
```

Comportamento: system prompt fundido no user; temperatura 0.6; parse de ``; tools desligadas em modelos reasoning; architect/reviewer/logic usam R1 quando a chave DeepSeek existe.

Skill: `pkf/skills/deepseek-r1-reasoning.md`.
