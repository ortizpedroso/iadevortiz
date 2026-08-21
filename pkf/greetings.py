from __future__ import annotations

import re

_GREETING_RE = re.compile(
    r"^(oi|olá|ola|hey|hi|hello|e aí|e ai|eae|bom dia|boa tarde|boa noite)[!.?\s]*$",
    re.IGNORECASE,
)


def is_greeting(text: str) -> bool:
    stripped = (text or "").strip()
    return bool(stripped and not stripped.startswith("/") and _GREETING_RE.match(stripped))


def greeting_reply() -> str:
    return (
        "Olá! Sou a PKF, assistente de desenvolvimento de software.\n\n"
        "Trabalhamos em ciclo **/spec → /build → /review**: primeiro alinhamos a spec, "
        "depois implementamos, e por fim revisamos.\n\n"
        "Descreva o que você quer construir (por exemplo: *cardápio digital whitelabel*) "
        "ou use `/spec` para começar."
    )
