from __future__ import annotations

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from pkf.config import GROQ_FALLBACK_MODEL, judge_model_for, providers
from pkf.providers import get_ai_client


def _judge_client(active_provider: str) -> tuple[AsyncOpenAI, str]:
    """Usa Groq/openai para o juiz quando o provedor ativo não tem o modelo."""
    judge_model = judge_model_for("")
    available = providers()
    for name in ("groq", "openai"):
        cfg = available.get(name)
        if cfg and cfg.api_key:
            client, config = get_ai_client(name)
            model = judge_model or config.model
            return client, model
    client, config = get_ai_client(active_provider)
    return client, judge_model or config.model or GROQ_FALLBACK_MODEL


async def evaluate_build_goal(
    active_provider: str,
    spec_excerpt: str,
    verify_text: str,
    goal: str | None = None,
) -> tuple[bool, str]:
    """Juiz independente: a spec/goal foi atendida?"""
    client, judge_model = _judge_client(active_provider)
    condition = goal or "A spec foi implementada com arquivos verificáveis no workspace."
    prompt = f"""Você é um juiz objetivo. Responda só JSON: {{"approved": true/false, "summary": "..."}}

Condição de parada:
{condition}

Trecho da spec:
{spec_excerpt[:2000]}

Resultado da verificação de build:
{verify_text[:1500]}

Aprovar apenas se houver evidência concreta de implementação. Se faltar index.html ou API prometida, reprove."""

    try:
        completion = await client.chat.completions.create(
            model=judge_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = (completion.choices[0].message.content or "").strip()
        import json
        import re

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return bool(data.get("approved")), str(data.get("summary", raw))[:500]
        return False, "Juiz não retornou JSON válido."
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError, APIConnectionError, APIStatusError, APITimeoutError) as exc:
        return False, f"Juiz indisponível: {exc}"
