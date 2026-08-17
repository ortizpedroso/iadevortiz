from __future__ import annotations

import re
from pathlib import Path

from pkf.config import pkf_dir

_APPROVED = re.compile(
    r"(?:^|\n)\s*(?:status|resultado)\s*:?\s*\n?\s*(?:aprovado|approved|ok|pass)\s*(?:$|\n)|(?:^|\n)\s*aprovado\s*(?:$|\n)",
    re.I | re.M,
)
_REJECTED = re.compile(
    r"(?:^|\n)\s*(?:status|resultado)\s*:?\s*\n?\s*(?:reprovado|rejected|failed|fail|pendente)\s*(?:$|\n)|(?:^|\n)\s*reprovado\s*(?:$|\n)",
    re.I | re.M,
)
_ISSUE_LINE = re.compile(r"^\s*[-*]\s+(?:\[.\]\s+)?(.+)$", re.M)


def latest_review_path(workspace_root: Path, spec_name: str | None) -> Path | None:
    reviews_dir = pkf_dir(workspace_root) / "reviews"
    if not reviews_dir.is_dir():
        return None
    if spec_name:
        exact = reviews_dir / f"{spec_name}.md"
        if exact.is_file():
            return exact
    candidates = sorted(reviews_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def parse_review_status(review_text: str) -> tuple[bool, list[str]]:
    """Interpreta relatório do reviewer. Espera linha 'Status: APROVADO' ou 'Status: REPROVADO'."""
    text = (review_text or "").strip()
    if not text:
        return False, ["Review vazio"]

    if _APPROVED.search(text) and not _REJECTED.search(text):
        issues = _extract_issues(text)
        real_issues = [
            i for i in issues if i and "nenhuma" not in i.lower() and "nenhum" not in i.lower()
        ]
        if not real_issues:
            return True, []
        return False, real_issues

    if _REJECTED.search(text):
        return False, _extract_issues(text)

    lower = text.lower()
    if "sem lacunas" in lower or "nenhuma lacuna" in lower or "aprovado sem ressalvas" in lower:
        return True, []
    if "aprovado" in lower and "reprovado" not in lower and "lacuna" not in lower:
        return True, []

    issues = _extract_issues(text)
    if issues:
        return False, issues
    if any(k in lower for k in ("lacuna", "falta", "bug", "problema", "não atende", "nao atende")):
        return False, [text[:500]]
    return False, ["Review inconclusivo — marque Status: APROVADO ou REPROVADO"]


def _extract_issues(text: str) -> list[str]:
    issues = [m.group(1).strip() for m in _ISSUE_LINE.finditer(text) if m.group(1).strip()]
    if issues:
        return issues[:12]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("-")]
    return [ln.lstrip("- ").strip() for ln in lines[:12] if ln.lstrip("- ").strip()]


def load_latest_review(workspace_root: Path, spec_name: str | None) -> str:
    path = latest_review_path(workspace_root, spec_name)
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
