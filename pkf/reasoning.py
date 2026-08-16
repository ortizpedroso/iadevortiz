from __future__ import annotations

import os
import re

THINKING_BLOCK = re.compile(r"<\s*think\s*>(.*?)<\s*/\s*think\s*>", re.S | re.I)
EMPTY_THINKING = re.compile(r"<\s*think\s*>\s*<\s*/\s*think\s*>", re.S | re.I)

_REASONING_MODEL_HINTS = ("reasoner", "deepseek-r1", "r1-distill", "qwq")


def is_reasoning_model(model: str) -> bool:
    model_l = (model or "").lower()
    return any(hint in model_l for hint in _REASONING_MODEL_HINTS)


def reasoning_agents() -> frozenset[str]:
    raw = os.getenv("PKF_REASONING_AGENTS", "architect,reviewer,logic").strip()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def agent_uses_reasoning(agent_name: str, model: str) -> bool:
    if is_reasoning_model(model):
        return True
    return agent_name in reasoning_agents() and bool(os.getenv("PKF_REASONING_MODEL", "").strip())


def reasoning_temperature() -> float:
    raw = os.getenv("PKF_REASONING_TEMPERATURE", "0.6").strip()
    try:
        value = float(raw)
    except ValueError:
        return 0.6
    return max(0.0, min(value, 2.0))


def completion_params_for_model(model: str) -> dict:
    if not is_reasoning_model(model):
        return {}
    return {"temperature": reasoning_temperature()}


def adapt_messages_for_reasoning(messages: list[dict]) -> list[dict]:
    """DeepSeek-R1 recomenda evitar system prompt; instruções vão no user."""
    system_parts: list[str] = []
    adapted: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            content = (msg.get("content") or "").strip()
            if content:
                system_parts.append(content)
            continue
        payload = dict(msg)
        if role == "user" and system_parts:
            prefix = "\n\n".join(system_parts)
            user_text = (msg.get("content") or "").strip()
            payload["content"] = f"{prefix}\n\n---\n\n{user_text}" if user_text else prefix
            system_parts = []
        adapted.append(payload)
    if system_parts:
        adapted.insert(0, {"role": "user", "content": "\n\n".join(system_parts)})
    return _preserve_tool_messages(messages, adapted)


def _preserve_tool_messages(original: list[dict], adapted: list[dict]) -> list[dict]:
    if not any(m.get("role") == "tool" for m in original):
        return adapted
    merged: list[dict] = []
    adapted_iter = iter(adapted)
    for msg in original:
        role = msg.get("role")
        if role == "system":
            continue
        if role in {"tool", "assistant"} and msg.get("tool_calls"):
            merged.append(msg)
            continue
        next_adapted = next(adapted_iter, None)
        if next_adapted and next_adapted.get("role") == role:
            merged.append(next_adapted)
            continue
        merged.append(msg)
    return merged


def parse_thinking(content: str, reasoning_content: str | None = None) -> tuple[str, str]:
    thinking_parts: list[str] = []
    if reasoning_content and reasoning_content.strip():
        thinking_parts.append(reasoning_content.strip())
    if content:
        for block in THINKING_BLOCK.findall(content):
            text = block.strip()
            if text:
                thinking_parts.append(text)
    answer = EMPTY_THINKING.sub("", content or "")
    answer = THINKING_BLOCK.sub("", answer).strip()
    return "\n\n".join(thinking_parts), answer


def prepare_messages_for_api(messages: list[dict], model: str, agent_name: str) -> list[dict]:
    if not agent_uses_reasoning(agent_name, model):
        return messages
    return adapt_messages_for_reasoning(messages)
