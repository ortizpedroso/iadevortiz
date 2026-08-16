from __future__ import annotations

import re


def explain_provider_error(provider: str, exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    lowered = text.lower()
    connection = any(token in lowered for token in ("connection", "connect", "timeout", "refused", "offline"))

    if "429" in text or "rate_limit" in lowered or "rate limit" in lowered:
        wait = _extract_retry_minutes(text)
        wait_hint = f" Tente de novo em ~{wait} min." if wait else ""
        return (
            "Todos os provedores gratuitos atingiram o limite momentâneo."
            f"{wait_hint}\n\n"
            "A PKF tenta 9Router → tier → multi-chave → provedor direto (Groq, Gemini, Kimi). "
            "Configure NINEROUTER_URL + combo free no dashboard ou chaves extras (GROQ_API_KEY_2)."
        )

    if provider == "ollama" and connection:
        return (
            "O Ollama não está rodando em http://localhost:11434.\n\n"
            "1. Instale: https://ollama.com/download\n"
            "2. Abra o aplicativo Ollama no Windows\n"
            "3. No terminal: ollama pull llama3:8b\n"
            "4. Recarregue esta página e envie de novo.\n\n"
            "Se preferir nuvem: pare a UI (Ctrl+C) e rode python -m pkf kimi --ui"
        )
    if provider == "kimi" and ("api" in lowered or "401" in lowered or "key" in lowered):
        return "Falha no Kimi. Confira MOONSHOT_API_KEY no arquivo .env."
    if provider == "groq" and ("api" in lowered or "401" in lowered or "key" in lowered):
        return (
            "Falha no Groq. Crie uma chave grátis em https://console.groq.com/keys "
            "e configure GROQ_API_KEY no .env."
        )
    if provider == "gemini" and ("api" in lowered or "401" in lowered or "key" in lowered):
        return (
            "Falha no Gemini. Crie uma chave grátis em https://aistudio.google.com/apikey "
            "e configure GEMINI_API_KEY no .env."
        )
    if provider == "ninerouter" and ("401" in lowered or "key" in lowered or "unauthorized" in lowered):
        return (
            "Falha no 9Router. Confira NINEROUTER_URL e NINEROUTER_KEY no .env "
            "(Dashboard → Keys no 9Router)."
        )
    if provider == "ninerouter" and ("503" in lowered or "unavailable" in lowered):
        wait = _extract_retry_minutes(text)
        wait_hint = f" Tente em ~{wait} min." if wait else ""
        return f"9Router: todos os provedores indisponíveis.{wait_hint} Verifique o dashboard do 9Router."
    if connection:
        return f"Não foi possível conectar ao provedor '{provider}'. {text}"
    return f"Erro no provedor '{provider}': {text}"


def _extract_retry_minutes(text: str) -> int | None:
    match = re.search(r"try again in (\d+)m", text.lower())
    if match:
        return int(match.group(1))
    return None
