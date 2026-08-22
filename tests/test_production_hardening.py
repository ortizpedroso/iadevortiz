"""Produção: auth, preview, deploy e run_command."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pkf.config import validate_production_config
from pkf.tools.impl import run_command
from pkf.workspace import Workspace


def test_validate_production_config_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("PKF_ENV", "production")
    monkeypatch.delenv("PKF_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="PKF_AUTH_TOKEN ausente"):
        validate_production_config()


def test_validate_production_config_rejects_weak_token(monkeypatch):
    monkeypatch.setenv("PKF_ENV", "production")
    monkeypatch.setenv("PKF_AUTH_TOKEN", "teste123")
    with pytest.raises(RuntimeError, match="fraco"):
        validate_production_config()


def test_validate_production_config_accepts_strong_token(monkeypatch):
    monkeypatch.setenv("PKF_ENV", "production")
    monkeypatch.setenv("PKF_AUTH_TOKEN", "a" * 32)
    validate_production_config()


def test_run_command_blocked_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv("PKF_ENV", "production")
    monkeypatch.delenv("PKF_ALLOW_RUN_COMMAND", raising=False)
    ws = Workspace(tmp_path)
    out = run_command(ws, "python --version")
    assert "desabilitado" in out.lower()


def test_set_env_keys_preserves_existing_auth_token(tmp_path: Path):
    env = tmp_path / ".env"
    manual = "manual-secret-token-32chars-minimum!!"
    env.write_text(f"PKF_AUTH_TOKEN={manual}\n", encoding="utf-8")
    snippet = r"""
if ! grep -q '^PKF_AUTH_TOKEN=' .env; then
  echo 'PKF_AUTH_TOKEN=teste123' >> .env
fi
"""
    subprocess.run(["/usr/bin/bash", "-c", snippet], cwd=tmp_path, check=True, text=True)  # noqa: S603
    assert env.read_text(encoding="utf-8").strip() == f"PKF_AUTH_TOKEN={manual}"


def test_set_env_keys_script_uses_conditional_auth_write():
    script = Path("deploy/hostinger/set-env-keys.sh").read_text(encoding="utf-8")
    assert "if ! grep -q '^PKF_AUTH_TOKEN=' .env" in script
    assert "set_kv_default NINEROUTER_MODEL" in script


def test_set_env_keys_script_migrates_weak_auth_token():
    script = Path("deploy/hostinger/set-env-keys.sh").read_text(encoding="utf-8")
    assert "migrate_weak_auth_token" in script
    assert "teste123" in script


def test_frontend_ws_uses_subprotocol_and_query_fallback():
    api = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    assert "pkf-token." in api
    assert "wsProtocols" in api
    ws_fn = api.split("export function wsUrl")[1].split("export ")[0]
    assert "?token=" in ws_fn


def test_health_public_payload_minimal():
    src = Path("pkf/web/server.py").read_text(encoding="utf-8")
    assert '"auth_required"' in src
    assert 'async def health():' in src or "async def health(" in src
    assert "ninerouter_ok" not in src.split("async def health")[1].split("async def preview")[0]


def test_frontend_preview_url_uses_preview_token():
    api = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    fn = api.split("export async function previewUrl")[1].split("export ")[0]
    assert "preview_token" in fn
    assert "getToken()" not in fn


def test_iframe_sandbox_without_same_origin():
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "allow-same-origin" not in app
