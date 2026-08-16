# Router híbrido PKF + 9Router

A PKF usa **9Router como gateway primário** e **router nativo como fallback**.

## Fluxo

```
PKF ProviderPool
  1. ninerouter#0  → 9Router (OpenCode Free, Kiro, combos, multi-conta)
  2. groq#0, groq#1 → suas chaves diretas (tiers)
  3. gemini#0      → tier cheap/free
```

Quando 9Router retorna 429/503, a PKF rotaciona para o próximo slot (Groq/Gemini direto).

## Configuração

```env
NINEROUTER_URL=http://127.0.0.1:20128
PKF_PROVIDER=ninerouter
NINEROUTER_KEY=local
NINEROUTER_MODEL=oc/big-pickle
NINEROUTER_SEARCH_MODEL=tavily

# Fallback nativo
PKF_PROVIDER_TIERS=subscription,cheap,free
PKF_TIER_CHEAP=groq,gemini
GROQ_API_KEY=...
GEMINI_API_KEY=...
```

## Docker

```bash
docker compose --profile router up -d
```

## Dashboard 9Router

1. Conecte **OpenCode Free** (sem auth)
2. Opcional: **Kiro OAuth** (~50 créd/mês)
3. Crie combo: `oc/big-pickle → kr/glm-5 → groq/...`
4. Copie API key do dashboard → `NINEROUTER_KEY`

## Web search

Com `NINEROUTER_URL`, usa `POST /v1/search`. Fallback: Tavily ou Brave no `.env`.
