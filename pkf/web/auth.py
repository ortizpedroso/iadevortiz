from __future__ import annotations

import os

from fastapi import HTTPException, Request, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware

from pkf.config import auth_token, is_production
from pkf.web.preview_tokens import validate_preview_token
from pkf.web.rate_limit import limiter


def auth_enforced() -> bool:
    """Exige autenticação fora de loopback ou quando PKF_REQUIRE_AUTH=1."""
    if os.getenv("PKF_REQUIRE_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    host = os.getenv("PKF_HOST", "127.0.0.1").strip().lower()
    return host not in {"127.0.0.1", "localhost", "::1"}


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.query_params.get("token") or request.headers.get("X-PKF-Token")


def _extract_ws_token(websocket: WebSocket) -> str | None:
    proto = websocket.headers.get("sec-websocket-protocol", "")
    for part in proto.split(","):
        candidate = part.strip()
        if candidate.startswith("pkf-token."):
            return candidate[len("pkf-token.") :]
    token = websocket.query_params.get("token") or websocket.headers.get("X-PKF-Token")
    return token


def require_auth_token(token: str | None) -> None:
    expected = auth_token()
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="Token inválido ou ausente.")


def check_ws_auth(websocket: WebSocket) -> bool:
    expected = auth_token()
    if auth_enforced() and not expected:
        return False
    if not expected:
        return True
    token = _extract_ws_token(websocket)
    return token == expected


def _public_paths() -> set[str]:
    return {"/api/health", "/", "/ws", "/favicon.ico"}


def _is_preview_path(path: str) -> bool:
    return path == "/preview" or path.startswith("/preview/")


def _preview_rel_path(path: str) -> str:
    if path == "/preview":
        return ""
    return path[len("/preview/") :]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not _is_preview_path(request.url.path):
            # unsafe-inline ainda necessário para o bundle Vite/React (C-M4: remoção quebra a UI).
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: blob:; "
                "connect-src 'self' ws: wss:; "
                "frame-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'"
            )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        expected = auth_token()
        if auth_enforced() and not expected:
            raise HTTPException(
                status_code=503,
                detail="Servidor não configurado: PKF_AUTH_TOKEN ausente.",
            )
        if is_production() and not expected:
            raise HTTPException(
                status_code=503,
                detail="Servidor não configurado: PKF_AUTH_TOKEN ausente em produção.",
            )

        path = request.url.path
        if path.startswith("/assets/") or path in _public_paths():
            return await call_next(request)

        if _is_preview_path(path):
            preview_token = request.query_params.get("preview_token")
            if preview_token and validate_preview_token(preview_token, _preview_rel_path(path)):
                return await call_next(request)
            if not expected:
                return await call_next(request)
            token = _extract_token(request)
            if token == expected:
                return await call_next(request)
            raise HTTPException(status_code=401, detail="Token de preview inválido ou ausente.")

        if not expected and not auth_enforced():
            return await call_next(request)

        if limiter.auth_locked(request):
            raise HTTPException(status_code=429, detail="Muitas tentativas de autenticação. Aguarde alguns minutos.")

        token = _extract_token(request)
        if token != expected:
            limiter.record_auth_failure(request)
            raise HTTPException(status_code=401, detail="Token inválido ou ausente.")
        return await call_next(request)
