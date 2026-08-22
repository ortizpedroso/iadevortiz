from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

REQUIRED_STACK_KEYS = ("frontend", "backend", "database", "deploy")


@dataclass
class SpecDocument:
    title: str
    body: str = ""
    status: str = "pending_approval"
    suggested_stack: dict[str, str] = field(default_factory=dict)
    confirmed_stack: dict[str, str] = field(default_factory=dict)

    @property
    def effective_stack(self) -> dict[str, str]:
        merged = dict(self.suggested_stack)
        merged.update({k: v for k, v in self.confirmed_stack.items() if v})
        return merged

    def to_markdown(self) -> str:
        meta = {
            "title": self.title,
            "status": self.status,
            "suggested_stack": self.suggested_stack,
            "confirmed_stack": self.confirmed_stack,
        }
        front = json.dumps(meta, ensure_ascii=False, indent=2)
        return f"---\n{front}\n---\n\n{self.body.strip()}\n"

    def to_preview_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "status": self.status,
            "suggested_stack": self.suggested_stack,
            "confirmed_stack": self.confirmed_stack,
            "effective_stack": self.effective_stack,
            "body": self.body,
            "markdown": self.to_markdown(),
        }


def validate_spec_substance(content: str) -> str | None:
    """Rejeita specs sem corpo substancial (além do frontmatter JSON)."""
    doc = parse_spec(content)
    body = doc.body.strip()
    if len(body) >= 300:
        return None
    sections = re.split(r"^#{1,3}\s+.+$", body, flags=re.MULTILINE)
    substantive = [part.strip() for part in sections if part.strip() and len(part.strip()) >= 40]
    if len(substantive) >= 2:
        return None
    return (
        "Erro: spec sem substância suficiente. Inclua contexto, requisitos e critérios de aceite "
        "(mínimo ~300 caracteres no corpo ou pelo menos 2 seções com conteúdo real). "
        "Não salve apenas uma frase genérica."
    )


def parse_spec_meta(content: str) -> dict | None:
    match = FRONTMATTER_RE.match(content or "")
    if not match:
        return None
    try:
        meta = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return meta if isinstance(meta, dict) else None


def validate_suggested_stack(meta: dict | None, stack: dict[str, str]) -> str | None:
    raw = (meta or {}).get("suggested_stack")
    if isinstance(raw, list):
        return (
            "suggested_stack malformado: veio como lista de rótulos "
            '(ex.: ["frontend", "backend"]). Use objeto JSON com valores reais, '
            'ex.: {"frontend": "React", "backend": "PHP", "database": "MySQL", "deploy": "Docker"}.'
        )
    for key in REQUIRED_STACK_KEYS:
        value = str((stack or {}).get(key, "")).strip()
        if not value:
            return (
                f"suggested_stack incompleto: a chave '{key}' está ausente ou vazia. "
                "Preencha frontend, backend, database e deploy com tecnologias concretas."
            )
    return None


def parse_spec(content: str) -> SpecDocument:
    match = FRONTMATTER_RE.match(content or "")
    if not match:
        return SpecDocument(title="Spec", body=content or "", status="approved")
    try:
        meta = json.loads(match.group(1))
    except json.JSONDecodeError:
        return SpecDocument(title="Spec", body=content, status="approved")
    if not isinstance(meta, dict):
        meta = {}
    body = content[match.end() :].strip()
    return SpecDocument(
        title=str(meta.get("title") or "Spec"),
        body=body,
        status=str(meta.get("status") or "pending_approval"),
        suggested_stack=_stack_dict(meta.get("suggested_stack")),
        confirmed_stack=_stack_dict(meta.get("confirmed_stack")),
    )


def render_spec(
    title: str,
    context: str,
    requirements: str,
    suggested_stack: dict[str, str],
    out_of_scope: str = "Nenhum",
    files: str = "A definir na implementação",
    acceptance: str = "",
) -> str:
    stack_lines = "\n".join(f"- **{k}:** {v}" for k, v in suggested_stack.items()) or "- A definir"
    body = f"""# Contexto
{context.strip()}

# Requisitos
{requirements.strip()}

# Stack sugerida (editável pelo usuário)
{stack_lines}

# Fora de escopo
{out_of_scope.strip()}

# Arquivos impactados
{files.strip()}

# Critérios de aceite
{acceptance.strip() or "- A definir com o usuário"}"""
    doc = SpecDocument(
        title=title,
        status="pending_approval",
        suggested_stack=suggested_stack,
        body=body,
    )
    return doc.to_markdown()


def _stack_dict(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if v}
