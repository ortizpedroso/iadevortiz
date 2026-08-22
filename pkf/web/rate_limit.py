from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request


class RateLimiter:
    """Limitador simples em memória por chave (IP + rota)."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._auth_failures: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _prune(self, key: str, window: int, store: dict[str, list[float]]) -> list[float]:
        now = time.time()
        recent = [t for t in store[key] if now - t < window]
        store[key] = recent
        return recent

    def check(self, request: Request, *, limit: int, window: int, scope: str) -> None:
        key = f"{scope}:{self._client_ip(request)}"
        hits = self._prune(key, window, self._hits)
        if len(hits) >= limit:
            raise HTTPException(status_code=429, detail="Muitas requisições. Tente novamente em instantes.")
        hits.append(time.time())
        self._hits[key] = hits

    def record_auth_failure(self, request: Request) -> None:
        key = self._client_ip(request)
        failures = self._prune(key, 300, self._auth_failures)
        failures.append(time.time())
        self._auth_failures[key] = failures

    def check_ws(self, websocket, *, limit: int, window: int, scope: str) -> None:
        forwarded = websocket.headers.get("x-forwarded-for", "")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        elif websocket.client:
            ip = websocket.client.host
        else:
            ip = "unknown"
        key = f"{scope}:{ip}"
        hits = self._prune(key, window, self._hits)
        if len(hits) >= limit:
            raise HTTPException(status_code=429, detail="Muitas conexões WebSocket. Aguarde.")
        hits.append(time.time())
        self._hits[key] = hits

    def auth_locked(self, request: Request, *, max_failures: int = 10, window: int = 300) -> bool:
        key = self._client_ip(request)
        failures = self._prune(key, window, self._auth_failures)
        return len(failures) >= max_failures


limiter = RateLimiter()
