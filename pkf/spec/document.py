from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


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
