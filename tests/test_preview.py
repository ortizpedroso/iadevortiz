from pathlib import Path

import pytest
from fastapi import HTTPException

from pkf.web.preview import find_preview_entry, preview_path
from pkf.workspace import Workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "style.css").write_text("body{}", encoding="utf-8")
    (tmp_path / ".pkf" / "specs").mkdir(parents=True)
    return Workspace(tmp_path)


def test_find_preview_entry(workspace: Workspace):
    assert find_preview_entry(workspace) == "index.html"


def test_preview_blocks_internal_pkf_files(workspace: Workspace):
    with pytest.raises(HTTPException) as exc:
        preview_path(workspace, ".pkf/session.json")
    assert exc.value.status_code == 403
