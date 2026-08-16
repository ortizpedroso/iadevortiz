# Router nativo PKF (fallback direto)

Usado quando 9Router não está configurado ou após esgotar slots do gateway.
Veja também `9router-hybrid.md`.
## Tiers (fallback 3 camadas)

```env
PKF_PROVIDER_TIERS=subscription,cheap,free
PKF_TIER_SUBSCRIPTION=groq,kimi
PKF_TIER_CHEAP=gemini
PKF_TIER_FREE=groq
PKF_GROQ_FALLBACK_MODEL=llama-3.1-8b-instant
```

Ordem: tenta **subscription** → escala para **cheap** → **free** quando há rate limit.

## Multi-chave (mesmo provedor)

```env
GROQ_API_KEY=gsk_primeira
GROQ_API_KEY_2=gsk_segunda
# ou
GROQ_API_KEYS=gsk_a,gsk_b
```

Rotação automática entre chaves antes de mudar de tier.

## Web search nativo

```env
TAVILY_API_KEY=tvly-...
# ou
BRAVE_SEARCH_API_KEY=...
```

Tool `web_search` para architect e generalista.

## Compactação RTK

Tool results grandes são comprimidos (head + hash + tail) em `compact.py` antes de ir ao modelo.
