from pathlib import Path

import pytest

from pkf.tools.impl import read_file, write_file
from pkf.workspace import Workspace, WorkspaceError


def test_resolve_keeps_paths_inside_workspace(tmp_path: Path):
    ws = Workspace(tmp_path)
    target = ws.resolve("src/app.py")
    assert target == tmp_path / "src" / "app.py"


def test_resolve_blocks_escape(tmp_path: Path):
    ws = Workspace(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.resolve("../secret.txt")


def test_secret_file_is_blocked(tmp_path: Path):
    ws = Workspace(tmp_path)
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    assert "bloqueado" in read_file(ws, ".env").lower()
    assert "bloqueada" in write_file(ws, ".env", "x").lower()


def test_write_and_read_roundtrip(tmp_path: Path):
    ws = Workspace(tmp_path)
    result = write_file(ws, "pkf_app/hello.py", "print('ok')\n")
    assert "gravado" in result.lower()
    assert read_file(ws, "pkf_app/hello.py") == "print('ok')\n"
