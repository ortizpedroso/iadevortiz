from pathlib import Path

from pkf.projects.manager import (
    load_pinned_projects,
    set_project_pinned,
    sort_projects,
)


def test_pin_and_sort_projects(tmp_path: Path):
    root = tmp_path
    (root / "projects" / "alpha").mkdir(parents=True)
    (root / "projects" / "beta").mkdir(parents=True)
    (root / "projects" / "zebra").mkdir(parents=True)

    set_project_pinned(root, "zebra", True)
    assert load_pinned_projects(root) == ["zebra"]

    projects = [
        {"slug": "alpha", "name": "Alpha"},
        {"slug": "beta", "name": "Beta"},
        {"slug": "zebra", "name": "Zebra"},
    ]
    sorted_projects = sort_projects(projects, root)
    assert sorted_projects[0]["slug"] == "zebra"
    assert sorted_projects[0]["pinned"] is True
    assert [p["slug"] for p in sorted_projects[1:]] == ["alpha", "beta"]

    set_project_pinned(root, "zebra", False)
    assert load_pinned_projects(root) == []
