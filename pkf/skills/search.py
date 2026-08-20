from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
_TOKEN = re.compile(r"[a-z0-9áàâãéêíóôõúüç]+", re.IGNORECASE)
AUTO_LOAD_THRESHOLD = 3.5


@dataclass
class SkillEntry:
    skill_id: str
    path: Path
    title: str
    body: str
    aliases: list[str]


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], avg_len: float, df: dict[str, int], n_docs: int) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    k1, b = 1.2, 0.75
    doc_len = len(doc_tokens)
    tf: dict[str, int] = {}
    for t in doc_tokens:
        tf[t] = tf.get(t, 0) + 1
    score = 0.0
    for term in query_tokens:
        if term not in tf:
            continue
        freq = tf[term]
        idf = math.log(1 + (n_docs - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
        denom = freq + k1 * (1 - b + b * doc_len / max(avg_len, 1))
        score += idf * (freq * (k1 + 1)) / denom
    return score


def _parse_skill(path: Path) -> SkillEntry:
    text = path.read_text(encoding="utf-8").strip()
    title = path.stem.replace("-", " ").replace("_", " ")
    aliases = [path.stem.lower(), path.stem.replace("_", "-").lower()]
    first_line = text.splitlines()[0] if text else ""
    if first_line.startswith("#"):
        title = first_line.lstrip("#").strip()
    return SkillEntry(skill_id=path.stem, path=path, title=title, body=text, aliases=aliases)


def list_skills() -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    skills_dir = _PKG_ROOT / "skills"
    if skills_dir.is_dir():
        for path in sorted(skills_dir.glob("*.md")):
            entries.append(_parse_skill(path))
    templates = _PKG_ROOT / "templates"
    if templates.is_dir():
        for path in sorted(templates.glob("*.md")):
            entry = _parse_skill(path)
            entry.skill_id = f"template-{path.stem}"
            entries.append(entry)
    return entries


def search_skills(query: str, limit: int = 5) -> list[tuple[SkillEntry, float]]:
    skills = list_skills()
    if not skills:
        return []
    q = _tokenize(query)
    if not q:
        return []

    docs = []
    df: dict[str, int] = {}
    for skill in skills:
        corpus = " ".join([skill.skill_id, skill.title, " ".join(skill.aliases), skill.body[:1500]])
        tokens = _tokenize(corpus)
        docs.append((skill, tokens))
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1

    avg_len = sum(len(t) for _, t in docs) / max(len(docs), 1)
    n_docs = len(docs)
    ranked: list[tuple[SkillEntry, float]] = []
    q_lower = query.lower()
    for skill, tokens in docs:
        score = _bm25_score(q, tokens, avg_len, df, n_docs)
        if skill.skill_id.lower() in q_lower or skill.title.lower() in q_lower:
            score += 5.0
        for alias in skill.aliases:
            if alias in q_lower:
                score += 4.0
        if score > 0:
            ranked.append((skill, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:limit]


def resolve_skills(query: str, project_slug: str | None = None) -> str:
    """Retorna skills relevantes: BM25 + fallback por slug."""
    blocks: list[str] = []
    ranked = search_skills(query or project_slug or "")
    if ranked:
        best, score = ranked[0]
        if score >= AUTO_LOAD_THRESHOLD:
            blocks.append(_format_skill(best))
        elif len(ranked) > 1:
            hints = ", ".join(f"{s.skill_id} ({sc:.1f})" for s, sc in ranked[:3])
            blocks.append(f"Skills candidatas (use skill_search): {hints}")

    slug = (project_slug or "").lower()
    if slug and not blocks:
        for skill, _ in ranked:
            sid = skill.skill_id.lower().replace("_", "-")
            if sid in slug or slug in sid or "template-" + slug.replace("-", "_") in sid:
                blocks.append(_format_skill(skill))
                break
    return "\n\n---\n\n".join(blocks)


def _format_skill(skill: SkillEntry) -> str:
    body = skill.body
    if len(body) > 2500:
        body = body[:2500] + "\n…"
    return f"### Skill: {skill.title}\n{body}"


def skill_search_tool_output(query: str) -> str:
    ranked = search_skills(query, limit=5)
    if not ranked:
        return "Nenhuma skill encontrada."
    lines = ["Skills encontradas (BM25):"]
    loaded = None
    for skill, score in ranked:
        mark = ""
        if loaded is None and score >= AUTO_LOAD_THRESHOLD:
            loaded = skill
            mark = " [AUTO-CARREGADA]"
        lines.append(f"- {skill.skill_id} (score={score:.2f}){mark}")
    if loaded:
        lines.append("\nConteúdo carregado:\n" + _format_skill(loaded))
    return "\n".join(lines)
