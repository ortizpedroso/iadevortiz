"""WebSocket session bootstrap resilience."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from pkf.provider_pool import ProviderPool, ProviderSlot
from pkf.router import Router
from pkf.web.server import create_app
from pkf.workspace import Workspace


def test_ws_session_survives_db_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("PKF_AUTH_TOKEN", "test-token-32-characters-minimum!!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://pkf:bad@localhost:5432/pkf")
    monkeypatch.setenv("PKF_HOST", "127.0.0.1")
    ws = Workspace(tmp_path)
    pool = ProviderPool(
        slots=[ProviderSlot(slot_id="m", provider="mock", api_key="k", tier="free", model="m")]
    )
    router = Router("mock", ws, ui_mode=True, client=MagicMock(), provider_pool=pool)
    app = create_app(router)
    client = TestClient(app)
    auth_value = "test-token-32-characters-minimum!!"
    with client.websocket_connect("/ws", subprotocols=[f"pkf-token.{auth_value}"]) as sock:
        data = sock.receive_json()
        assert data["type"] == "session"
        assert data.get("database_degraded") is True


def test_ws_session_subprotocol_without_query_token(monkeypatch, tmp_path):
    """H2: auth via subprotocol apenas — sem ?token= na URL."""
    monkeypatch.setenv("PKF_AUTH_TOKEN", "test-token-32-characters-minimum!!")
    monkeypatch.setenv("PKF_HOST", "127.0.0.1")
    ws = Workspace(tmp_path)
    pool = ProviderPool(
        slots=[ProviderSlot(slot_id="m", provider="mock", api_key="k", tier="free", model="m")]
    )
    router = Router("mock", ws, ui_mode=True, client=MagicMock(), provider_pool=pool)
    app = create_app(router)
    client = TestClient(app)
    auth_value = "test-token-32-characters-minimum!!"
    with client.websocket_connect("/ws", subprotocols=[f"pkf-token.{auth_value}"]) as sock:
        data = sock.receive_json()
        assert data["type"] == "session"
