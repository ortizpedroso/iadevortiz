from __future__ import annotations

import re


def explain_provider_error(provider: str, exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    lowered = text.lower()
    connection = any(token in lowered for token in ("connection", "connect", "timeout", "refused", "offline"))

    if "429" in text or "rate_limit" in lowered or "rate limit" in lowered:
        wait = _extract_retry_minutes(text)
        wait_hint = f" Tente de novo em ~{wait} min." if wait else " Aguarde alguns minutos e tente de novo."
        return (
            "Limite diário de tokens do Groq atingido (plano gratuito).\n\n"
            f"{wait_hint}\n\n"
            "Opções:\n"
            "1. Aguardar o reset (meia-noite UTC ou quando indicado acima)\n"
            "2. Trocar o modelo no .env da VPS para um mais leve:\n"
            "   OPENAI_MODEL=llama-3.1-8b-instant\n"
            "3. Usar outro provedor grátis (Gemini): GEMINI_API_KEY + PKF_PROVIDER=gemini\n"
            "4. Upgrade em https://console.groq.com/settings/billing"
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
    if connection:
        return f"Não foi possível conectar ao provedor '{provider}'. {text}"
    return f"Erro no provedor '{provider}': {text}"


def _extract_retry_minutes(text: str) -> int | None:
    match = re.search(r"try again in (\d+)m", text.lower())
    if match:
        return int(match.group(1))
    return None
