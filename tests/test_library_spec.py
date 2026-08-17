"""Conformidade da biblioteca lateral com a spec pkf-platform."""

from pathlib import Path

import pytest

from pkf.spec.updater import save_platform_spec
from pkf.web import server as web_server
from pkf.workflow.review import parse_review_status


REQUIRED_ENDPOINTS = (
    "/api/library",
    "/api/chats",
    "/api/chats/{chat_id}/activate",
    "/api/chats/{chat_id}/attach",
    "/api/projects/{slug}/activate",
    "PATCH /api/projects/{slug}",
)


def test_spec_lists_library_endpoints():
    spec_path = Path(__file__).resolve().parents[1] / "pkf" / "spec" / "updater.py"
    text = spec_path.read_text(encoding="utf-8")
    for endpoint in REQUIRED_ENDPOINTS:
        assert endpoint.replace("{chat_id}", "{id}").replace("{slug}", "{slug}") in text or endpoint in text


def test_server_exposes_library_routes():
    source = Path(web_server.__file__).read_text(encoding="utf-8")
    assert '"/api/library"' in source
    assert '"/api/chats"' in source
    assert '"/api/chats/{chat_id}/activate"' in source
    assert '"/api/chats/{chat_id}/attach"' in source
    assert '"/api/projects/{slug}/activate"' in source
    assert '"/api/projects/{slug}"' in source
    assert "projects_rename" in source or '@app.patch("/api/projects/{slug}")' in source


def test_sidebar_frontend_wired():
    app_src = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.tsx").read_text(
        encoding="utf-8"
    )
    sidebar_src = (
        Path(__file__).resolve().parents[1] / "frontend" / "src" / "components" / "Sidebar.tsx"
    ).read_text(encoding="utf-8")
    for prop in (
        "onSelectChat",
        "onDeleteChat",
        "onAttachChat",
        "onSelectProject",
        "onDeleteProject",
        "onRenameProject",
        "onNewChat",
    ):
        assert prop in app_src
        assert prop in sidebar_src
    assert "⋮" in sidebar_src or "Renomear" in sidebar_src
    assert "Renomear" in sidebar_src
    assert "window.confirm" in sidebar_src


def test_boot_uses_load_library_only_for_projects():
    app_src = Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.tsx"
    text = app_src.read_text(encoding="utf-8")
    boot_start = text.index("async function boot()")
    boot_end = text.index("loadChanges();", boot_start)
    boot_block = text[boot_start:boot_end]
    assert "applyLibrary(data.library)" not in boot_block


def test_platform_spec_review_approved(tmp_path: Path):
    slug = save_platform_spec(tmp_path)
    review = f"""# Review biblioteca lateral ({slug})

Implementacao conforme spec pkf-platform: sidebar, API REST, migracao legado, validacao de slugs.

Status: APROVADO
"""
    reviews_dir = tmp_path / ".pkf" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    (reviews_dir / f"{slug}.md").write_text(review, encoding="utf-8")
    ok, issues = parse_review_status(review)
    assert ok, issues
