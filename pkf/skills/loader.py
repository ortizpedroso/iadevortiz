from __future__ import annotationsfrom pkf.skills.search import resolve_skillsdef load_skills_for_project(project_slug: str | None = None, query: str = "") -> str:
    """Carrega skills via BM25 + fallback por slug do projeto."""
    return resolve_skills(query, project_slug)
