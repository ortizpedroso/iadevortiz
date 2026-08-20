from __future__ import annotations

import hashlib
import re

from pkf.config import compaction_budget


def compact_messages(messages: list[dict], model: str = "") -> list[dict]:
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
            "[Histórico compactado para economizar contexto]\n"
            + "\n".join(summary_lines[:24])
        ),
    }
    return system + [note] + recent


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
