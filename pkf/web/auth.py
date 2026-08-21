from __future__ import annotations

from fastapi import HTTPException, Request, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware

from pkf.config import auth_token, is_production


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.query_params.get("token") or request.headers.get("X-PKF-Token")


def _extract_ws_token(websocket: WebSocket) -> str | None:
    token = websocket.query_params.get("token") or websocket.headers.get("X-PKF-Token")
    if token:
        return token
    proto = websocket.headers.get("sec-websocket-protocol", "")
    if proto.startswith("pkf-token."):
        return proto[len("pkf-token.") :]
    return None


def require_auth_token(token: str | None) -> None:
    expected = auth_token()
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="Token inválido ou ausente.")


def check_ws_auth(websocket: WebSocket) -> bool:
    expected = auth_token()
    if is_production() and not expected:
        return False
    if not expected:
        return True
    token = _extract_ws_token(websocket)
    return token == expected


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not request.url.path.startswith("/preview"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
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
        if is_production() and not expected:
            raise HTTPException(
                status_code=503,
                detail="Servidor não configurado: PKF_AUTH_TOKEN ausente em produção.",
            )
        if not expected:
            return await call_next(request)
        if request.url.path.startswith("/assets/") or request.url.path in {
            "/api/health",
            "/",
            "/ws",
            "/favicon.ico",
        }:
            return await call_next(request)
        token = _extract_token(request)
        if token != expected:
            raise HTTPException(status_code=401, detail="Token inválido ou ausente.")
        return await call_next(request)
