import json
from pathlib import Path

import pytest

from pkf.semantic_index import rebuild_index, semantic_search
from pkf.tools.impl import edit_file, write_file
from pkf.workspace import Workspace


@pytest.fixture(autouse=True)
def test_semantic_embedder(monkeypatch):
    monkeypatch.setenv("PKF_TEST_SEMANTIC", "1")


def test_semantic_search_finds_related_concept(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(
        ws,
        "auth.py",
        (
            "def check_ws_auth(token: str) -> bool:\n"
            '    """Valida token de autenticação WebSocket."""\n'
            "    return bool(token)\n"
        ),
    )
    result = semantic_search(ws, "autenticação websocket", top_k=3)
    assert "auth.py" in result
    assert "check_ws_auth" in result


def test_incremental_reindex_updates_single_file(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(ws, "a.py", "def alpha():\n    return 1\n")
    write_file(ws, "b.py", "def beta():\n    return 2\n")
    index_path = tmp_path / ".pkf" / "index" / "semantic.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    paths_before = {c["path"] for c in data["chunks"]}
    assert "a.py" in paths_before and "b.py" in paths_before

    edit_file(ws, "a.py", "return 1", "return 42")
    data_after = json.loads(index_path.read_text(encoding="utf-8"))
    a_chunks = [c for c in data_after["chunks"] if c["path"] == "a.py"]
    b_chunks = [c for c in data_after["chunks"] if c["path"] == "b.py"]
    assert a_chunks
    assert b_chunks
    assert any("42" in c.get("text", "") for c in a_chunks)


def test_search_code_semantic_mode(tmp_path: Path):
    ws = Workspace(tmp_path)
    from pkf.tools.impl import search_code

    write_file(
        ws,
        "security.py",
        (
            "def validate_session_cookie(value: str) -> bool:\n"
            '    """Validação de sessão por cookie."""\n'
            "    return len(value) > 8\n"
        ),
    )
    result = search_code(ws, "validação sessão cookie", mode="semantic")
    assert "security.py" in result


def test_rebuild_index(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(ws, "x.py", "def foo():\n    pass\n")
    msg = rebuild_index(ws)
    assert "semântico" in msg.lower() or "chunks" in msg.lower()


def test_semantic_fallback_without_sentence_transformers(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("PKF_TEST_SEMANTIC", raising=False)
    import pkf.semantic_index as si

    si._MODEL = None

    def _missing_model():
        try:
            raise ImportError("sentence_transformers unavailable")
        except ImportError:
            si._MODEL = "test"
            return si._MODEL

    monkeypatch.setattr(si, "_get_model", _missing_model)
    ws = Workspace(tmp_path)
    write_file(ws, "auth.py", "def login():\n    return True\n")
    result = semantic_search(ws, "login auth")
    assert "auth.py" in result

