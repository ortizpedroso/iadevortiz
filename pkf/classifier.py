from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from pkf.agents.prompts import DEVELOPER_AGENTS

VALID_AGENTS = {"architect", "frontend", "backend", "logic", "reviewer", "tester", "generalista"}
VALID_KINDS = {"question", "feature", "change", "command", "review_request", "test_request"}

KEYWORD_MAP = {
    "architect": (
        "arquitetura",
        "arquiteto",
        "desenhe o sistema",
        "estrutura do projeto",
        "módulos",
        "trade-off",
        "tradeoff",
    ),
    "frontend": (
        "frontend",
        "front-end",
        "react",
        "css",
        "html",
        "botão",
        "botao",
        "interface",
        "componente",
        "ui",
        "ux",
        "página",
        "pagina",
        "layout",
    ),
    "backend": (
        "backend",
        "back-end",
        "api",
        "banco de dados",
        "servidor",
        "endpoint",
        "auth",
        "autenticação",
        "autenticacao",
        "sql",
        "orm",
    ),
    "logic": (
        "algoritmo",
        "otimizar",
        "otimização",
        "otimizacao",
        "lógica",
        "logica",
        "regra de negócio",
        "regra de negocio",
        "calcular",
    ),
    "reviewer": ("revise", "revisar", "code review", "revisor", "aponta bugs", "review"),
    "tester": ("teste", "testes", "pytest", "coverage", "tdd", "unit test"),
}

FEATURE_HINTS = ("crie", "criar", "implemente", "implementar", "adicione", "adicionar", "quero um", "preciso de um")
CHANGE_HINTS = ("mude", "mudar", "altere", "alterar", "ajuste", "corrigir", "corrija", "renomeie")
QUESTION_HINTS = ("o que", "como", "por que", "porque", "onde", "explique", "qual ")


@dataclass
class Intent:
    agent: str
    kind: str
    source: str


BUILD_AGENTS = {"frontend", "backend", "logic", "tester"}


def _agent_for_command(command: str, text: str, last_agent: str | None) -> str:
    if command == "/spec":
        return "architect"
    if command == "/review":
        return "reviewer"
    if command == "/build":
        for agent in ("backend", "frontend", "logic"):
            if any(keyword in text for keyword in KEYWORD_MAP[agent]):
                return agent
        if last_agent in BUILD_AGENTS:
            return last_agent
        return "frontend"
    return last_agent if last_agent in DEVELOPER_AGENTS else "architect"


def classify_intent(user_input: str, last_agent: str | None = None) -> Intent:
    text = user_input.lower().strip()
    if text.startswith(("/spec", "/build", "/review")):
        command = next(cmd for cmd in ("/spec", "/build", "/review") if text.startswith(cmd))
        agent = _agent_for_command(command, text, last_agent)
        return Intent(agent=agent, kind="command", source="command")
    if text.startswith(("/status", "/agents", "/graph", "/help", "/workspace")):
        return Intent(agent=last_agent or "generalista", kind="command", source="command")

    kind = _kind_from_text(text)
    if kind == "review_request":
        return Intent(agent="reviewer", kind=kind, source="keywords")
    if kind == "test_request":
        return Intent(agent="tester", kind=kind, source="keywords")

    for agent, keywords in KEYWORD_MAP.items():
        if any(keyword in text for keyword in keywords):
            return Intent(agent=agent, kind=kind, source="keywords")

    if last_agent in DEVELOPER_AGENTS and _kind_from_text(text) in {"feature", "change", "review_request", "test_request"}:
        return Intent(agent=last_agent, kind=_kind_from_text(text), source="sticky")

    if _kind_from_text(text) == "feature":
        return Intent(agent="architect", kind="feature", source="keywords")
    return Intent(agent="generalista", kind=_kind_from_text(text), source="fallback")


def _kind_from_text(text: str) -> str:
    if any(hint in text for hint in ("revise", "review", "code review")):
        return "review_request"
    if any(hint in text for hint in ("teste", "testes", "pytest", "tdd")):
        return "test_request"
    if any(hint in text for hint in CHANGE_HINTS):
        return "change"
    if any(hint in text for hint in FEATURE_HINTS):
        return "feature"
    if text.endswith("?") or any(hint in text for hint in QUESTION_HINTS):
        return "question"
    return "question"


async def classify_intent_llm(
    client: AsyncOpenAI,
    model: str,
    user_input: str,
    last_agent: str | None = None,
) -> Intent:
    fallback = classify_intent(user_input, last_agent)
    prompt = (
        "Classifique a mensagem para uma IA de desenvolvimento.\n"
        f"Agentes válidos: {sorted(VALID_AGENTS)}\n"
        f"Tipos válidos: {sorted(VALID_KINDS)}\n"
        f"Último agente: {last_agent or 'nenhum'}\n"
        "Responda SOMENTE um JSON: {\"agent\": \"...\", \"kind\": \"...\"}\n"
        f"Mensagem: {user_input}"
    )
    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Você classifica intenções. Responda só JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        raw = completion.choices[0].message.content or ""
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return fallback
        data = json.loads(match.group(0))
        agent = data.get("agent", fallback.agent)
        kind = data.get("kind", fallback.kind)
        if agent not in VALID_AGENTS:
            agent = fallback.agent
        if kind not in VALID_KINDS:
            kind = fallback.kind
        return Intent(agent=agent, kind=kind, source="llm")
    except Exception:
        return fallback
