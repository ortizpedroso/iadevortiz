from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def ninerouter_enabled() -> bool:
    return bool(os.getenv("NINEROUTER_URL", "").strip())


def ninerouter_origin() -> str:
    return os.getenv("NINEROUTER_URL", "http://127.0.0.1:20128").strip().rstrip("/")


def ninerouter_api_key() -> str:
    return os.getenv("NINEROUTER_KEY", "").strip() or os.getenv("NINEROUTER_API_KEY", "").strip()


def ninerouter_chat_base_url() -> str:
    return f"{ninerouter_origin()}/v1"


def ninerouter_chat_model() -> str:
    return (
        os.getenv("NINEROUTER_MODEL", "").strip()
        or os.getenv("PKF_NINEROUTER_MODEL", "").strip()
        or "oc/big-pickle"
    )


def ninerouter_search_model() -> str:
    return os.getenv("NINEROUTER_SEARCH_MODEL", "tavily").strip() or "tavily"


def ninerouter_health() -> tuple[bool, str]:
    if not ninerouter_enabled():
        return False, "NINEROUTER_URL não configurado"
    url = f"{ninerouter_origin()}/v1/models"
    headers = {"Accept": "application/json"}
    key = ninerouter_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            if resp.status != 200:
                return False, f"HTTP {resp.status}"
            return True, "ok"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.reason}"
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return False, str(exc)


def is_ninerouter_auth_error(detail: str) -> bool:
    text = (detail or "").lower()
    if "401" in text or "403" in text:
        return True
    if "api key required" in text:
        return True
    return "ninerouter_key ausente" in text


def ninerouter_auth_warning(reason: str = "401") -> str:
    label = reason.strip() or "401"
    if "ausente" in label.lower():
        label = "401"
    return (
        f"[9Router] Chave inválida ou ausente ({label}). PKF seguirá com Gemini/Groq.\n"
        "Para corrigir na VPS: cd /opt/pkf && bash deploy/hostinger/fix-ninerouter-key.sh\n"
        "Ou manualmente: túnel `ssh -L 20128:127.0.0.1:20128 root@VPS`, gere uma chave sk-... "
        "no dashboard do 9Router, defina NINEROUTER_KEY=sk-... no .env, e rode "
        "`docker compose --profile router up -d pkf --force-recreate`."
    )


def ninerouter_should_skip() -> tuple[bool, str]:
    """Pula 9Router na sessão quando a chave está ausente ou o health retorna 401/403."""
    if not ninerouter_enabled():
        return False, ""
    if not ninerouter_api_key():
        return True, "NINEROUTER_KEY ausente"
    ok, detail = ninerouter_health()
    if not ok and is_ninerouter_auth_error(detail):
        return True, detail
    return False, detail if not ok else ""


def ninerouter_web_search(query: str, max_results: int = 5) -> str:
    text = (query or "").strip()
    if not text:
        return "Informe uma query de busca."
    if not ninerouter_enabled():
        return "9Router não configurado (NINEROUTER_URL)."
    payload = {
        "model": ninerouter_search_model(),
        "query": text,
        "max_results": max(1, min(int(max_results or 5), 10)),
    }
    url = f"{ninerouter_origin()}/v1/search"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {ninerouter_api_key()}",
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return f"9Router search falhou (HTTP {exc.code}): {raw[:300]}"
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        return f"9Router search indisponível: {exc}"

    if not isinstance(body, dict):
        return f"Resposta inválida do 9Router para: {text}"
    results = body.get("results") or []
    answer = body.get("answer")
    lines = [f"Resultados (9Router/{body.get('provider', payload['model'])}) para: {text}"]
    if answer:
        lines.append(f"\nResumo: {answer}")
    if not results and not answer:
        errors = body.get("errors") or []
        if errors:
            return f"9Router search sem resultados: {errors[0]}"
        return f"Nenhum resultado para: {text}"
    for item in results:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or "(sem título)"
        url_item = item.get("url") or ""
        snippet = (item.get("snippet") or item.get("content") or "").strip()
        lines.append(f"\n- **{title}**")
        if url_item:
            lines.append(f"  {url_item}")
        if snippet:
            lines.append(f"  {snippet[:400]}")
    return "\n".join(lines)
