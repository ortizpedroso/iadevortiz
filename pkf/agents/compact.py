from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from openai import APIConnectionError, APIStatusError, APITimeoutError

from pkf.config import compaction_budget

if TYPE_CHECKING:
    from openai import AsyncOpenAI

COMPACT_MARKER = "[Histórico compactado para economizar contexto]"

_SUMMARY_TEMPLATE = """\
Resuma o progresso desta conversa de desenvolvimento no formato abaixo. Mantenha cada seção mesmo se vazia.

## Objetivo
[1-2 frases do que o usuário está tentando alcançar]

## Detalhes Importantes
[restrições, decisões tomadas e por quê, fatos relevantes, ou "(nenhum)"]

## Estado do Trabalho
### Concluído
[trabalho finalizado, fatos verificados, ou "(nenhum)"]
### Ativo
[trabalho em andamento, investigação parcial, ou "(nenhum)"]
### Bloqueado
[bloqueios, comandos falhando, incertezas, ou "(nenhum)"]

## Próximo Passo
[ação concreta imediata, ou "(nenhum)"]

## Arquivos Relevantes
[caminho: por que importa, ou "(nenhum)"]
"""

_REQUIRED_SECTIONS = (
    "## Objetivo",
    "## Detalhes Importantes",
    "## Estado do Trabalho",
    "### Concluído",
    "### Ativo",
    "### Bloqueado",
    "## Próximo Passo",
    "## Arquivos Relevantes",
)


def compact_messages(messages: list[dict], model: str = "") -> list[dict]:
    """Compactação síncrona (mecânica) — usada em testes e como fallback."""
    return _compact_messages_mechanical(messages, model)


async def compact_messages_llm(
    messages: list[dict],
    model: str,
    client: AsyncOpenAI,
) -> list[dict]:
    """Compacta histórico antigo via resumo estruturado LLM; fallback mecânico se falhar."""
    budget = compaction_budget(model)
    trimmed = _compress_tool_results(messages, budget["tool_chars"])
    system_msgs = [m for m in trimmed if m.get("role") == "system"]
    rest = [m for m in trimmed if m.get("role") != "system"]
    if len(rest) <= budget["max_messages"]:
        return system_msgs + rest

    split = _split_point(rest, budget["keep_recent"])
    old, recent = rest[:split], rest[split:]
    previous = _extract_previous_summary(system_msgs)

    try:
        summary = await _llm_structured_summary(client, model, old, previous)
    except (APIConnectionError, APIStatusError, APITimeoutError, RuntimeError, ValueError, AttributeError):
        return _compact_messages_mechanical(messages, model)

    note = {"role": "system", "content": f"{COMPACT_MARKER}\n{summary.strip()}"}
    base_system = [m for m in system_msgs if not _is_compaction_note(m)]
    return base_system + [note] + recent


def _compact_messages_mechanical(messages: list[dict], model: str = "") -> list[dict]:
    """Reduz tokens: comprime tool results (estilo RTK) e resume mensagens antigas."""
    budget = compaction_budget(model)
    max_msgs = budget["max_messages"]
    tool_chars = budget["tool_chars"]
    keep_recent = budget["keep_recent"]

    trimmed = _compress_tool_results(messages, tool_chars)
    system = [m for m in trimmed if m.get("role") == "system"]
    rest = [m for m in trimmed if m.get("role") != "system"]
    if len(rest) <= max_msgs:
        return system + rest

    split = _split_point(rest, keep_recent)
    old, recent = rest[:split], rest[split:]
    summary_lines: list[str] = []
    for msg in old:
        role = msg.get("role", "?")
        content = (msg.get("content") or "").replace("\n", " ")[:180]
        if not content and msg.get("tool_calls"):
            content = f"tool_calls={len(msg['tool_calls'])}"
        if content:
            summary_lines.append(f"- {role}: {content}")
    note = {
        "role": "system",
        "content": (
            f"{COMPACT_MARKER}\n"
            + "\n".join(summary_lines[:24])
        ),
    }
    base_system = [m for m in system if not _is_compaction_note(m)]
    return base_system + [note] + recent


def _is_compaction_note(msg: dict) -> bool:
    content = msg.get("content") or ""
    return msg.get("role") == "system" and COMPACT_MARKER in content


def _extract_previous_summary(system_msgs: list[dict]) -> str | None:
    for msg in reversed(system_msgs):
        if not _is_compaction_note(msg):
            continue
        content = str(msg.get("content") or "")
        if COMPACT_MARKER in content:
            return content.split(COMPACT_MARKER, 1)[-1].strip()
        return content.strip()
    return None


def _format_messages_for_summary(messages: list[dict]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "?")
        content = (msg.get("content") or "").strip()
        if not content and msg.get("tool_calls"):
            content = f"[{len(msg['tool_calls'])} tool_calls]"
        if content:
            lines.append(f"{role}: {content[:4000]}")
    return "\n\n".join(lines) or "(nenhuma mensagem)"


async def _llm_structured_summary(
    client: AsyncOpenAI,
    model: str,
    old_messages: list[dict],
    previous_summary: str | None,
) -> str:
    transcript = _format_messages_for_summary(old_messages)
    user_parts: list[str] = []
    if previous_summary:
        user_parts.append(
            "Resumo anterior (combine com o novo — mantenha objetivos/decisões que ainda valem, "
            "atualize o que mudou, remova só o que foi resolvido; não descarte o resumo anterior inteiro):\n\n"
            f"{previous_summary}"
        )
    user_parts.append(f"Mensagens a resumir:\n\n{transcript}")

    completion = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SUMMARY_TEMPLATE},
            {"role": "user", "content": "\n\n---\n\n".join(user_parts)},
        ],
        temperature=0,
    )
    raw = (completion.choices[0].message.content or "").strip()
    if not raw:
        raise RuntimeError("compactação LLM retornou vazio")
    return _ensure_template_sections(raw)


def _ensure_template_sections(text: str) -> str:
    missing = [section for section in _REQUIRED_SECTIONS if section not in text]
    if not missing:
        return text
    suffix = "\n".join(f"{section}\n(nenhum)" for section in missing)
    return f"{text.rstrip()}\n\n{suffix}"


def _split_point(rest: list[dict], keep: int) -> int:
    if len(rest) <= keep:
        return 0
    split = len(rest) - keep
    while split > 0 and rest[split].get("role") == "tool":
        split -= 1
    if split > 0 and rest[split - 1].get("tool_calls"):
        split -= 1
    return split


def _compress_tool_results(messages: list[dict], max_chars: int) -> list[dict]:
    out: list[dict] = []
    for msg in messages:
        if msg.get("role") != "tool":
            out.append(msg)
            continue
        content = _normalize_whitespace(msg.get("content") or "")
        if len(content) <= max_chars:
            out.append({**msg, "content": content})
            continue
        copy = dict(msg)
        copy["content"] = _rtk_shrink(content, max_chars)
        out.append(copy)
    return out


def _normalize_whitespace(text: str) -> str:
    collapsed = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r"[ \t]{2,}", " ", collapsed).strip()


def _rtk_shrink(content: str, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    head = max_chars // 2
    tail = max(240, max_chars // 4)
    digest = hashlib.sha1(content.encode("utf-8", errors="ignore"), usedforsecurity=False).hexdigest()[:10]
    lines = content.count("\n") + 1
    omitted = len(content) - head - tail
    return (
        f"{content[:head].rstrip()}\n\n"
        f"…[{omitted} chars omitidos · {lines} linhas · sha1:{digest}]…\n\n"
        f"{content[-tail:].lstrip()}"
    )
