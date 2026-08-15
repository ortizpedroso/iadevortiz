from pathlib import Path

from pkf.projects.manager import slug_from_request
from pkf.workspace import Workspace


def test_project_folder_is_created(tmp_path: Path):
    ws = Workspace(tmp_path)
    ws.set_project(slug_from_request("Cardápio digital whitelabel"))
    assert ws.project == "cardapio-digital-whitelabel"
    assert (tmp_path / "projects" / "cardapio-digital-whitelabel").is_dir()
    assert ws.resolve("index.html") == tmp_path / "projects" / "cardapio-digital-whitelabel" / "index.html"
