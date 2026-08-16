# DeepSeek-R1 — reasoning na PKF

Baseado no repositório [deepseek-ai/DeepSeek-R1](https://github.com/deepseek-ai/DeepSeek-R1) (documentação oficial do modelo, não código de agente).

## O que o repo é

- Paper + README + pesos no Hugging Face — **não** é um framework CLI como Qwen Code.
- API OpenAI-compatível: `https://api.deepseek.com`, modelo `deepseek-reasoner`.
- Modelos destilados (1.5B–70B) rodam via vLLM/SGLang; a PKF usa a **API**, não treina nem hospeda 671B.

## Configuração na PKF

```env
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat          # chat geral
DEEPSEEK_REASONER_MODEL=deepseek-reasoner
PKF_REASONING_MODEL=deepseek-reasoner # architect/reviewer/logic
PKF_REASONING_AGENTS=architect,reviewer,logic
PKF_REASONING_TEMPERATURE=0.6
PKF_WEB_SEARCH_FORMAT=deepseek        # citações [citation:N]
```

Com `DEEPSEEK_API_KEY`, architect/reviewer/logic usam `deepseek-reasoner` automaticamente.

## Comportamento implementado

1. **Sem system prompt** — instruções do agente são fundidas no user (recomendação R1).
2. **Temperatura 0.6** em modelos reasoning (`reasoner`, `r1`, `qwq`).
3. **Parse ``** — raciocínio separado da resposta; evento SSE `reasoning`.
4. **Tools desligadas** em modelos reasoning (API R1 não é ideal para tool calling).
5. **Web search** — template oficial DeepSeek com `[webpage N]` e `[citation:N]`.

## Uso híbrido com 9Router

Mantenha `PKF_PROVIDER=ninerouter` e adicione `DEEPSEEK_API_KEY` + `PKF_ARCHITECT_MODEL=deepseek-reasoner` se o 9Router expuser DeepSeek; ou use `PKF_PROVIDER=deepseek` só para specs/reviews.

## Referência rápida (README oficial)

- Evite system prompt; instruções no user.
- Temperature 0.5–0.7 (default 0.6).
- Forçar raciocínio: resposta deve iniciar com bloco think quando o modelo pular o passo.
