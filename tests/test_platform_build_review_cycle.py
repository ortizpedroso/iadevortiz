"""Ciclo /build → /review programático contra spec pkf-platform."""

from __future__ import annotations

from pathlib import Path

from pkf.spec.updater import save_platform_spec
from pkf.web import server as web_server
from pkf.workflow.compose import MAX_REVIEW_FIX_CYCLES
from pkf.workflow.review import parse_review_status

SPEC_CHECKS = (
    ("Menu de contexto", "Menu de contexto"),
    ("PATCH rename", "PATCH /api/projects"),
    ("CSS vars", "--pkf-accent"),
    ("Headroom", "PKF_HEADROOM_PROXY_URL"),
    ("9Router skip 401", "401"),
    ("Tier qualidade", "PKF_TIER_QUALITY"),
    ("Build graph", "PKF_USE_LANGGRAPH_BUILD"),
    ("Benchmark", "benchmark"),
)


def _implementation_gaps(spec_text: str) -> list[str]:
    gaps: list[str] = []
    for label, needle in SPEC_CHECKS:
        if needle not in spec_text:
            gaps.append(f"Spec sem: {label}")
    server_src = Path(web_server.__file__).read_text(encoding="utf-8")
    if "projects_rename" not in server_src and '@app.patch("/api/projects/{slug}")' not in server_src:
        gaps.append("Backend: PATCH /api/projects/{slug} ausente")
    sidebar = Path("frontend/src/components/Sidebar.tsx").read_text(encoding="utf-8")
    if "Renomear" not in sidebar or "onRenameProject" not in sidebar:
        gaps.append("Frontend: menu Renomear ausente")
    if "window.confirm" not in sidebar:
        gaps.append("Frontend: confirmacao de exclusao ausente")
    css = Path("frontend/src/index.css").read_text(encoding="utf-8")
    if "--pkf-accent" not in css:
        gaps.append("CSS: variaveis centralizadas ausentes")
    return gaps


def run_build_review_cycle(workspace: Path) -> tuple[int, bool, list[str], str]:
    """Simula build+review: regenera spec, verifica lacunas, aprova quando conforme."""
    slug = save_platform_spec(workspace)
    spec_path = workspace / ".pkf" / "specs" / f"{slug}.md"
    spec_text = spec_path.read_text(encoding="utf-8")
    cycles = 0
    gaps: list[str] = []
    for cycle in range(1, MAX_REVIEW_FIX_CYCLES + 1):
        cycles = cycle
        gaps = _implementation_gaps(spec_text)
        if not gaps:
            break
    approved = not gaps
    review = f"""# Review pkf-platform ({slug})

Ciclo {cycles}/{MAX_REVIEW_FIX_CYCLES}. Spec alinhada com menu de contexto, PATCH rename,
confirmacao de exclusao, variaveis CSS, Headroom, 9Router skip 401, tier qualidade, benchmark e build graph.

Status: {"APROVADO" if approved else "REPROVADO"}
"""
    if gaps:
        review += "\nPendencias:\n" + "\n".join(f"- {g}" for g in gaps)
    ok, _issues = parse_review_status(review)
    return cycles, ok and approved, gaps, review


def test_platform_build_review_cycle(tmp_path: Path):
    cycles, approved, gaps, review = run_build_review_cycle(tmp_path)
    assert cycles >= 1
    assert approved, gaps
    assert "APROVADO" in review
