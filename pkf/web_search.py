from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from pkf.config import API_TIMEOUT
from pkf.deepseek import format_search_results, web_search_format
from pkf.ninerouter import ninerouter_enabled, ninerouter_web_search


def web_search_configured() -> bool:
    if ninerouter_enabled():
        return True
    return bool(os.getenv("TAVILY_API_KEY", "").strip() or os.getenv("BRAVE_SEARCH_API_KEY", "").strip())


def web_search(query: str, max_results: int = 5) -> str:
    text = (query or "").strip()
    if not text:
        return "Informe uma query de busca."
    max_results = max(1, min(int(max_results or 5), 10))

    if ninerouter_enabled():
        result = ninerouter_web_search(text, max_results)
        if "falhou" not in result.lower() and "indisponível" not in result.lower():
            return result
        if not os.getenv("TAVILY_API_KEY", "").strip() and not os.getenv("BRAVE_SEARCH_API_KEY", "").strip():
            return result

    if os.getenv("TAVILY_API_KEY", "").strip():
        return _tavily_search(text, max_results)
    if os.getenv("BRAVE_SEARCH_API_KEY", "").strip():
        return _brave_search(text, max_results)
    if ninerouter_enabled():
        return ninerouter_web_search(text, max_results)
    return (
        "Web search indisponível. Configure NINEROUTER_URL, TAVILY_API_KEY "
        "(https://tavily.com) ou BRAVE_SEARCH_API_KEY (https://brave.com/search/api/) no .env."
    )


def _tavily_search(query: str, max_results: int) -> str:
    payload = {
        "api_key": os.getenv("TAVILY_API_KEY", "").strip(),
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }
    status, body = _post_json("https://api.tavily.com/search", payload, timeout=30.0)
    if status != 200:
        return f"Tavily falhou (HTTP {status}): {_error_text(body)}"
    results = body.get("results") if isinstance(body, dict) else None
    answer = body.get("answer") if isinstance(body, dict) else None
    return _format_results(query, results or [], answer)


def _brave_search(query: str, max_results: int) -> str:
    url = (
        "https://api.search.brave.com/res/v1/web/search?"
        + urllib.parse.urlencode({"q": query, "count": max_results})
    )
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": os.getenv("BRAVE_SEARCH_API_KEY", "").strip(),
    }
    status, body = _request("GET", url, headers=headers, timeout=30.0)
    if status != 200:
        return f"Brave Search falhou (HTTP {status}): {_error_text(body)}"
    web = body.get("web") if isinstance(body, dict) else None
    results = web.get("results") if isinstance(web, dict) else None
    normalized = []
    for item in results or []:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("description"),
            }
        )
    return _format_results(query, normalized, None)


def _format_results(query: str, results: list, answer: str | None) -> str:
    if web_search_format() == "deepseek":
        normalized = []
        for item in results:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "snippet": item.get("snippet") or item.get("content"),
                }
            )
        if normalized or answer:
            formatted = format_search_results(query, normalized)
            if answer:
                return f"{formatted}\n\nResumo rápido: {answer}"
            return formatted
    if not results and not answer:
        return f"Nenhum resultado para: {query}"
    lines = [f"Resultados para: {query}"]
    if answer:
        lines.append(f"\nResumo: {answer}")
    for item in results:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or "(sem título)"
        url = item.get("url") or ""
        snippet = (item.get("snippet") or item.get("content") or "").strip()
        lines.append(f"\n- **{title}**")
        if url:
            lines.append(f"  {url}")
        if snippet:
            lines.append(f"  {snippet[:400]}")
    return "\n".join(lines)


def _error_text(body) -> str:
    if isinstance(body, dict):
        return str(body.get("error") or body.get("message") or body)
    return str(body)


def _post_json(url: str, payload: dict, timeout: float | None = None) -> tuple[int, object]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    return _request("POST", url, headers=headers, data=data, timeout=timeout)


def _request(
    method: str,
    url: str,
    headers: dict | None = None,
    data: bytes | None = None,
    timeout: float | None = None,
) -> tuple[int, object]:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout or API_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {"error": exc.reason}
        except json.JSONDecodeError:
            parsed = {"error": raw or exc.reason}
        return exc.code, parsed
