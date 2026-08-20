from __future__ import annotations

from fastapi import HTTPException, Request, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware

from pkf.config import auth_token


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.query_params.get("token") or request.headers.get("X-PKF-Token")


def _extract_ws_token(websocket: WebSocket) -> str | None:
    return websocket.query_params.get("token") or websocket.headers.get("X-PKF-Token")


def require_auth_token(token: str | None) -> None:
    expected = auth_token()
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="Token inválido ou ausente.")


def check_ws_auth(websocket: WebSocket) -> bool:
    expected = auth_token()
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
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        expected = auth_token()
        if not expected:
            return await call_next(request)
        if request.url.path.startswith("/assets/") or request.url.path in {
            "/api/health",
            "/",
            "/ws",
        }:
            return await call_next(request)
        token = _extract_token(request)
        if token != expected:
            raise HTTPException(status_code=401, detail="Token inválido ou ausente.")
        return await call_next(request)
