"""Testes da remediação de segurança (auditoria grupos A/B)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from pkf.config import is_secret_env_var, is_secret_filename
from pkf.router import Router
from pkf.tools.impl import _safe_subprocess_env, search_code
from pkf.web.auth import auth_enforced, check_ws_auth
from pkf.web.preview_tokens import issue_preview_token, validate_preview_token
from pkf.workspace import Workspace


@pytest.fixture
def router(tmp_path):
    ws = Workspace(tmp_path)
    from pkf.provider_pool import ProviderPool, ProviderSlot

    pool = ProviderPool(
        slots=[
            ProviderSlot(
                slot_id="mock-1",
                provider="mock",
                api_key="test-key",
                tier="free",
                model="mock-model",
            )
        ],
    )
    return Router("mock", ws, ui_mode=True, client=MagicMock(), provider_pool=pool)


def test_auth_enforced_on_non_loopback_bind(monkeypatch):
    monkeypatch.delenv("PKF_REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("PKF_HOST", "0.0.0.0")  # noqa: S104
    assert auth_enforced() is True


def test_auth_enforced_with_explicit_flag(monkeypatch):
    monkeypatch.setenv("PKF_HOST", "127.0.0.1")
    monkeypatch.setenv("PKF_REQUIRE_AUTH", "1")
    assert auth_enforced() is True


def test_preview_token_issue_and_validate(monkeypatch):
    monkeypatch.setenv("PKF_AUTH_TOKEN", "super-secret-auth-token-32chars")
    token, ttl = issue_preview_token("index.html")
    assert ttl > 0
    assert validate_preview_token(token, "index.html")
    assert not validate_preview_token(token, "other.html")


def test_preview_token_expired(monkeypatch):
    monkeypatch.setenv("PKF_AUTH_TOKEN", "super-secret-auth-token-32chars")
    token, _ = issue_preview_token("index.html")
    import pkf.web.preview_tokens as mod

    original = mod.time.time
    mod.time.time = lambda: original() + 3600
    try:
        assert not validate_preview_token(token, "index.html")
    finally:
        mod.time.time = original


def test_ws_auth_via_subprotocol(monkeypatch):
    monkeypatch.setenv("PKF_AUTH_TOKEN", "ws-token-32-characters-minimum")
    ws = MagicMock()
    ws.query_params = {}
    ws.headers = {"sec-websocket-protocol": "pkf-token.ws-token-32-characters-minimum"}
    assert check_ws_auth(ws) is True
    ws.headers = {"sec-websocket-protocol": "pkf-token.wrong"}
    assert check_ws_auth(ws) is False


def test_ws_auth_via_query_fallback(monkeypatch):
    monkeypatch.setenv("PKF_AUTH_TOKEN", "ws-token-32-characters-minimum")
    ws = MagicMock()
    ws.query_params = {"token": "ws-token-32-characters-minimum"}
    ws.headers = {}
    assert check_ws_auth(ws) is True


def test_secret_filename_patterns():
    assert is_secret_filename(".env")
    assert is_secret_filename(".env.production")
    assert is_secret_filename("secrets.env")
    assert is_secret_filename("cert.pem")
    assert not is_secret_filename("index.html")


def test_secret_env_var_patterns(monkeypatch):
    monkeypatch.setenv("PKF_AUTH_TOKEN", "x")
    monkeypatch.setenv("NINEROUTER_KEY", "y")
    env = _safe_subprocess_env()
    assert "PKF_AUTH_TOKEN" not in env
    assert "NINEROUTER_KEY" not in env
    assert is_secret_env_var("OPENAI_API_KEY")


def test_search_code_rejects_long_regex(tmp_path):
    ws = Workspace(tmp_path)
    long_pattern = "a" * 250
    out = search_code(ws, long_pattern)
    assert "muito longo" in out.lower()


def test_restore_chat_history_only_active_agent(router: Router):
    router._register_core_agents()
    router.cycle.last_agent = "architect"
    messages = [
        {"role": "user", "content": "primeira"},
        {"role": "assistant", "content": "resposta"},
    ]
    router.restore_chat_history(messages)
    architect_users = [m for m in router.agents["architect"].messages if m["role"] == "user"]
    generalista_users = [m for m in router.agents["generalista"].messages if m["role"] == "user"]
    assert len(architect_users) == 1
    assert len(generalista_users) == 0


def _mock_pool():
    from pkf.provider_pool import ProviderPool, ProviderSlot

    return ProviderPool(
        slots=[
            ProviderSlot(
                slot_id="mock-1",
                provider="mock",
                api_key="test-key",
                tier="free",
                model="mock-model",
            )
        ],
    )


def test_health_endpoint_minimal_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("PKF_AUTH_TOKEN", "")
    monkeypatch.setenv("PKF_HOST", "127.0.0.1")
    monkeypatch.delenv("PKF_ENV", raising=False)
    ws = Workspace(tmp_path)
    r = Router("mock", ws, ui_mode=True, client=MagicMock(), provider_pool=_mock_pool())
    from pkf.web.server import create_app

    app = create_app(r)
    client = TestClient(app)
    data = client.get("/api/health").json()
    assert set(data.keys()) <= {"ok", "auth_required"}
    assert data["ok"] is True


def test_preview_route_accepts_preview_token(monkeypatch, tmp_path):
    monkeypatch.setenv("PKF_AUTH_TOKEN", "super-secret-auth-token-32chars")
    ws = Workspace(tmp_path)
    (tmp_path / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    r = Router("mock", ws, ui_mode=True, client=MagicMock(), provider_pool=_mock_pool())
    from pkf.web.server import create_app

    app = create_app(r)
    client = TestClient(app)
    token, _ = issue_preview_token("index.html")
    res = client.get(f"/preview/index.html?preview_token={token}")
    assert res.status_code == 200


def test_docker_compose_requires_api_key():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert 'REQUIRE_API_KEY: "true"' in compose
    assert "pkf-admin-2026" not in compose


def test_deploy_uses_vps_host_secret():
    deploy = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")
    assert "secrets.VPS_HOST" in deploy
    assert "187.77.240.125" not in deploy
