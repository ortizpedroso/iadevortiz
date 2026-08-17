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
cd /opt/pkf && git pull && bash deploy/hostinger/update.sh
```

Inclui PostgreSQL, PKF (`:8765`) e Nginx opcional (`:8080` — evita conflito com Caddy na :80).

## Deploy automático (GitHub Actions)

Todo **push na `main`** dispara o workflow `.github/workflows/deploy.yml`:

1. SSH na VPS
2. `git pull origin main`
3. `bash deploy/hostinger/update.sh` (rebuild com `PKF_GIT_SHA` para invalidar cache do frontend)
4. Health check opcional com retry

### Secrets obrigatórios (cadastro manual, uma única vez)

Em **GitHub → Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Obrigatório | Descrição |
|---|---|---|
| `VPS_HOST` | Sim | IP ou hostname da VPS |
| `VPS_USER` | Sim | Usuário SSH (ex.: `root`) |
| `VPS_SSH_KEY` | Sim | Chave privada SSH (conteúdo completo do arquivo) |
| `VPS_PORT` | Não | Porta SSH (padrão `22` se omitido) |
| `VPS_HEALTHCHECK_URL` | Não | URL pública do health check (ex.: `http://SEU_IP:8765/api/health`) |

O Cursor **não** configura esses secrets — exige acesso à conta GitHub e à chave privada da VPS.

### Recomendação de segurança (não automatizada)

Gere uma chave **dedicada** só para deploy, em vez de reusar a chave pessoal:

```bash
ssh-keygen -t ed25519 -f deploy_key -C "github-actions-deploy"
# Na VPS: adicionar deploy_key.pub em ~/.ssh/authorized_keys
# No GitHub: VPS_SSH_KEY = conteúdo de deploy_key (privada)
```

Se o secret vazar, revogue só essa chave — sem comprometer a chave pessoal da conta.

## Comandos

| Comando | Função |
|---|---|
| `/spec` | Gera spec automática |
| `/build` | Pipeline em fases (backend→frontend) + review→fix loop |
| `/review` | Revisa código vs spec |
| `/goal` | Meta de parada do build |

## Interface (UI)

A UI moderna (Vite/React) é servida quando `frontend/dist/` existe (build Docker ou `npm run build`).

- **Visual:** tema escuro entre Claude e Cursor — rail lateral, chat centralizado, accent terracota
- **Painéis:** projeto/tarefas, spec (aprovação manual), preview embutido
- **Biblioteca lateral:** chats e projetos listados à esquerda — criar, selecionar, excluir e anexar chat a projeto
- **Auth:** modal de token (`PKF_AUTH_TOKEN`); health público reduzido
- **Acessibilidade:** skip link, `aria-live`, reduced motion

Deploy: [DEPLOY.md](DEPLOY.md)

## Router híbrido (recomendado para uso contínuo)

**9Router primário por padrão** quando `NINEROUTER_URL` está definida — não é mais necessário `PKF_PROVIDER=ninerouter`. O router nativo (Groq/Gemini/etc.) continua como fallback automático.

```bash
# VPS — subir PKF + 9Router
docker compose --profile router up -d
```

`.env` na VPS:

```env
NINEROUTER_URL=http://ninerouter:20128
NINEROUTER_KEY=sk-...                    # chave gerada no dashboard do 9Router
NINEROUTER_MODEL=oc/big-pickle
PKF_PROVIDER_TIERS=subscription,cheap,free
PKF_TIER_CHEAP=groq,gemini
GROQ_API_KEY=...              # fallback direto
GEMINI_API_KEY=...
```

No dashboard do 9Router (`http://127.0.0.1:20128`): conecte **OpenCode Free** e/ou **Kiro OAuth**, crie combo free.

### Erro 401 no 9Router

Se a chave estiver ausente ou inválida, a PKF **detecta no boot** (health check) e pula o 9Router — segue direto com Groq/Gemini, sem desperdiçar tentativa nem cooldown.

Log esperado:

```
[9Router] Chave inválida ou ausente (401). PKF seguirá com Gemini/Groq.
```

**Correção:**

```bash
cd /opt/pkf && bash deploy/hostinger/fix-ninerouter-key.sh
```

Ou manualmente: túnel `ssh -L 20128:127.0.0.1:20128 root@VPS`, gere uma chave `sk-...` no dashboard, defina `NINEROUTER_KEY=sk-...` no `.env`, e rode `docker compose --profile router up -d pkf --force-recreate`.

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

## Headroom (compressão de contexto, opt-in)

O [Headroom](https://github.com/headroomlabs-ai/headroom) comprime tool outputs, logs e histórico antes de enviar ao modelo. A PKF não implementa compressão própria — apenas aponta o cliente OpenAI para o proxy quando configurado.

**Subir o proxy localmente:**

```bash
pip install "headroom-ai[proxy]"
headroom proxy --port 8787
```

Configure o upstream real no ambiente do Headroom (Groq, OpenAI, etc.) conforme a [documentação do Headroom](https://headroomlabs-ai.github.io/headroom/quickstart/).

**Apontar a PKF:**

```env
PKF_HEADROOM_PROXY_URL=http://127.0.0.1:8787/v1
```

Com a variável definida, `get_ai_client()` usa essa URL como `base_url` (o provedor/modelo/chave continuam os de sempre). Sem a variável, comportamento idêntico ao anterior.

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

## Tier de qualidade (Claude via gateway)

Para `architect` e `reviewer` apenas — agentes de build (`frontend`, `backend`, `logic`, `tester`) **nunca** usam este tier.

O 9Router já roteia modelos Claude (`kr/claude-*`) via API OpenAI-compatible. Alternativa: qualquer gateway compatível (LiteLLM, etc.) registrado como provedor PKF.

```env
PKF_TIER_QUALITY=ninerouter
PKF_QUALITY_MODEL=kr/claude-sonnet-4.5
NINEROUTER_URL=http://ninerouter:20128
NINEROUTER_KEY=sk-...
```

Sem `PKF_TIER_QUALITY`, `architect` e `reviewer` usam o tier padrão (sem erro).
