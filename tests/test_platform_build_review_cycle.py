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
    ("Router-only", "PKF_ROUTER_ONLY"),
    ("OmniRoute", "OmniRoute"),
    ("Tier qualidade", "PKF_TIER_QUALITY"),
    ("Build graph", "PKF_USE_LANGGRAPH_BUILD"),
    ("Benchmark", "benchmark"),
    ("Verificação T3", "get_last_verification"),
    ("Segurança produção", "Segurança e produção"),
    ("Memória anti-fabricação", "Memória de sessão"),
    ("Classificador", "Classificador de intenção"),
    ("Auth token deploy", "não sobrescreve"),
    ("Preview isolado", "allow-same-origin"),
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
    set_env = Path("deploy/hostinger/set-env-keys.sh").read_text(encoding="utf-8")
    if "if ! grep -q '^PKF_AUTH_TOKEN=' .env" not in set_env:
        gaps.append("Deploy: PKF_AUTH_TOKEN ainda sobrescrito a cada update")
    if "set_kv_default NINEROUTER_MODEL" not in set_env:
        gaps.append("Deploy: NINEROUTER_MODEL ainda sobrescrito em set-env-keys")
    update_sh = Path("deploy/hostinger/update.sh").read_text(encoding="utf-8")
    if "?token=$(grep '^PKF_AUTH_TOKEN='" in update_sh:
        gaps.append("Deploy: update.sh ainda imprime token na URL")
    preview_py = Path("pkf/web/preview.py").read_text(encoding="utf-8")
    if "?token=" in preview_py:
        gaps.append("Preview: redirect ainda inclui token na query")
    app_tsx = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    if "allow-same-origin" in app_tsx:
        gaps.append("Preview: iframe ainda usa allow-same-origin")
    if "validate_production_config" not in Path("pkf/web/server.py").read_text(encoding="utf-8"):
        gaps.append("Backend: validate_production_config ausente no boot")
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
confirmacao de exclusao, variaveis CSS, Headroom, 9Router skip 401, tier qualidade, benchmark,
build graph, get_last_verification, hardening de producao (auth, preview, deploy).

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
