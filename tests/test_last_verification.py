"""Persistência e consulta do resultado real da verificação de build (T3)."""

from __future__ import annotations

import json

from pkf.config import pkf_dir
from pkf.tools.impl import get_last_verification, verify_build
from pkf.verify_store import load_last_verification
from pkf.workspace import Workspace
from pkf.workspace_index import begin_build_session, verify_workspace_files


def test_verify_build_persists_failure(tmp_path):
    ws = Workspace(tmp_path)
    text = verify_build(ws, phase="T3")
    assert "incompleto" in text.lower()
    path = pkf_dir(tmp_path) / "last_verify.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["ok"] is False
    assert data["phase"] == "T3"
    assert data["result"] == text
    assert data["details"]["reason"] == "no_build_session"


def test_get_last_verification_returns_persisted_error(tmp_path):
    ws = Workspace(tmp_path)
    expected = verify_build(ws, phase="T3")
    out = get_last_verification(ws)
    assert expected in out
    assert "falha" in out.lower()
    assert "T3" in out
    assert load_last_verification(tmp_path) is not None


def test_verify_build_persists_success(tmp_path):
    ws = Workspace(tmp_path)
    begin_build_session(ws)
    from pkf.tools.impl import write_file

    write_file(ws, "app.js", "console.log('ok')")
    text = verify_build(ws, phase="T3")
    data = json.loads((pkf_dir(tmp_path) / "last_verify.json").read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert verify_workspace_files(ws)["ok"] is True
    assert "Build verificado" in text
    assert "sucesso" in get_last_verification(ws).lower()
