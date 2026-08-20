from pathlib import Path

from pkf.tools.impl import edit_file, write_file
from pkf.workspace import Workspace
from pkf.workspace_index import list_changes


def test_edit_file_ambiguous_without_replace_all(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(ws, "a.py", "foo = 1\nbar = 1\n")
    original = (tmp_path / "a.py").read_text(encoding="utf-8")
    result = edit_file(ws, "a.py", "= 1", "= 2")
    assert "ambíguo" in result.lower()
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == original


def test_edit_file_replace_all(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(ws, "a.py", "foo = 1\nbar = 1\n")
    result = edit_file(ws, "a.py", "= 1", "= 2", replace_all=True)
    assert "2 substituição" in result
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "foo = 2\nbar = 2\n"


def test_edit_file_syntax_error_reverts(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(ws, "a.py", "def ok():\n    return 1\n")
    original = (tmp_path / "a.py").read_text(encoding="utf-8")
    result = edit_file(ws, "a.py", "def ok():", "def ok(")
    assert "sintaxe" in result.lower() or "syntax" in result.lower()
    assert "revertida" in result.lower()
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == original


def test_edit_file_valid_edit(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(ws, "a.py", 'msg = "hello world"\n')
    result = edit_file(ws, "a.py", "world", "PKF")
    assert "1 substituição" in result
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == 'msg = "hello PKF"\n'


def test_edit_file_identical_strings_error(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(ws, "a.py", 'msg = "hello world"\n')
    original = (tmp_path / "a.py").read_text(encoding="utf-8")
    result = edit_file(ws, "a.py", "world", "world")
    assert "idênticos" in result.lower()
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == original


def test_write_file_invalid_json_not_created(tmp_path: Path):
    ws = Workspace(tmp_path)
    target = tmp_path / "data.json"
    result = write_file(ws, "data.json", "{invalid")
    assert "json" in result.lower()
    assert "revertida" in result.lower()
    assert not target.exists()


def test_edit_file_records_diff_in_change_log(tmp_path: Path):
    ws = Workspace(tmp_path)
    write_file(ws, "a.py", "x = 1\n")
    edit_file(ws, "a.py", "x = 1", "x = 2")
    changes = list_changes(ws, limit=5)
    edit_entries = [c for c in changes if c.get("action") == "edit"]
    assert edit_entries
    snippet = edit_entries[-1]["snippet"]
    assert "old=" in snippet and "new=" in snippet
    assert "@@" in snippet or "---" in snippet
