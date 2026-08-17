from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from pkf.graph.project import ProjectGraph
from pkf.spec.store import load_spec
from pkf.workflow.compose import HANDOFF_API_PATH

FRONTEND_HINTS = ("ui", "interface", "html", "css", "react", "página", "pagina", "tela", "botão", "botao", "layout")
BACKEND_HINTS = ("api", "backend", "servidor", "endpoint", "auth", "banco", "database", "sql", "crud")
LOGIC_HINTS = ("regra", "negócio", "negocio", "algoritmo", "cálculo", "calculo", "whitelabel", "multi-tenant")
TEST_HINTS = ("teste", "testes", "pytest", "coverage", "tdd", "unit test")

PHASE_ORDER = ("backend", "logic", "frontend", "tester")


@dataclass
class BuildTask:
    agent: str
    node_id: str
    instruction: str
    acceptance: str = ""
    parallel: bool = True
    phase: int = 0


def plan_build(workspace_root, spec_name: str | None) -> list[BuildTask]:
    graph = ProjectGraph(workspace_root)
    body = ""
    stack: dict[str, str] = {}
    if spec_name:
        doc = load_spec(workspace_root, spec_name)
        if doc:
            body = doc.body
            stack = doc.effective_stack
    text = body.lower()
    tasks: list[BuildTask] = []

    def add(agent: str, node_id: str, focus: str, acceptance: str = "") -> None:
        stack_hint = ""
        if stack:
            stack_hint = "\nStack confirmada: " + ", ".join(f"{k}={v}" for k, v in stack.items())
        accept = acceptance or f"Entregar {focus} conforme a spec."
        instruction = _task_instruction(agent, node_id, focus, accept, stack_hint)
        tasks.append(
            BuildTask(
                agent=agent,
                node_id=node_id,
                acceptance=accept,
                instruction=instruction,
            )
        )

    if any(h in text for h in BACKEND_HINTS) or "backend" in stack or "database" in stack:
        add("backend", "backend", "API, persistência e serviços", "endpoints ou módulo backend funcional")
        _maybe_dynamic(graph, "backend", _extract_bullets(body, "api", "backend", "banco"))
    if any(h in text for h in LOGIC_HINTS):
        add("logic", "logic", "regras de negócio e whitelabel", "regras de negócio testáveis")
    if any(h in text for h in FRONTEND_HINTS) or "frontend" in stack:
        add("frontend", "frontend", "interface e assets públicos", "index.html ou UI navegável no preview")
        _maybe_dynamic(graph, "frontend", _extract_bullets(body, "frontend", "ui", "tela"))
    if any(h in text for h in TEST_HINTS):
        add("tester", "tester", "testes automatizados", "testes cobrindo critérios da spec")
    if not tasks:
        add("frontend", "frontend", "implementação principal da spec", "preview disponível com index.html")
    return _assign_phases(tasks)


def group_tasks_into_phases(tasks: list[BuildTask]) -> list[list[BuildTask]]:
    if not tasks:
        return []
    distinct_phases = {t.phase for t in tasks}
    if len(distinct_phases) > 1 or (distinct_phases and 0 not in distinct_phases):
        ordered = sorted(tasks, key=lambda t: (t.phase, t.agent))
    else:
        ordered = _assign_phases(list(tasks))
    max_phase = max(t.phase for t in ordered)
    phases: list[list[BuildTask]] = []
    for phase in range(max_phase + 1):
        group = [t for t in ordered if t.phase == phase]
        if group:
            phases.append(group)
    return phases


def _assign_phases(tasks: list[BuildTask]) -> list[BuildTask]:
    order = {name: index for index, name in enumerate(PHASE_ORDER)}
    for task in tasks:
        task.phase = order.get(task.agent, len(PHASE_ORDER))
    tasks.sort(key=lambda t: (t.phase, t.agent))
    return tasks


async def plan_build_llm(
    client: AsyncOpenAI,
    model: str,
    workspace_root,
    spec_name: str | None,
) -> list[BuildTask] | None:
    """Planner via LLM — retorna None se falhar (usa heurística)."""
    body = ""
    stack: dict[str, str] = {}
    if spec_name:
        doc = load_spec(workspace_root, spec_name)
        if doc:
            body = doc.body
            stack = doc.effective_stack
    if not body.strip():
        return None

    prompt = f"""Analise a spec e produza APENAS JSON válido para o build multiagente PKF.

Agentes disponíveis: backend, logic, frontend, tester
Ordem de fases: backend → logic → frontend → tester (dependências respeitadas)
Inclua só agentes necessários para a spec.

Formato:
{{"phases": [{{"agents": ["backend"], "focus": "..."}}, {{"agents": ["frontend"], "focus": "..."}}]}}

Spec:
{body[:4000]}

Stack: {json.dumps(stack, ensure_ascii=False)}
"""
    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = (completion.choices[0].message.content or "").strip()
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return None
        data = json.loads(match.group())
        phases = data.get("phases") or []
        tasks: list[BuildTask] = []
        for phase_index, phase in enumerate(phases):
            agents = phase.get("agents") or []
            focus = str(phase.get("focus") or "implementação conforme spec")
            if not isinstance(agents, list):
                continue
            for agent in agents:
                name = str(agent).strip().lower()
                if name not in PHASE_ORDER and name != "tester":
                    continue
                node_id = name if name != "tester" else "tester"
                instruction = _task_instruction(name, node_id, focus, f"Entregar {focus}", "")
                tasks.append(
                    BuildTask(
                        agent=name,
                        node_id=node_id,
                        acceptance=focus,
                        instruction=instruction,
                        phase=phase_index,
                    )
                )
        return tasks or None
    except Exception:
        return None


def plan_fix_tasks(spec_name: str | None, issues: list[str]) -> list[BuildTask]:
    """Gera tarefas de correção a partir dos problemas apontados no review."""
    joined = "\n".join(f"- {issue}" for issue in issues[:10])
    text = joined.lower()
    agents: list[str] = []
    if any(k in text for k in BACKEND_HINTS + ("api", "endpoint", "servidor")):
        agents.append("backend")
    if any(k in text for k in LOGIC_HINTS):
        agents.append("logic")
    if any(k in text for k in FRONTEND_HINTS + ("html", "css", "ui", "interface")):
        agents.append("frontend")
    if any(k in text for k in TEST_HINTS):
        agents.append("tester")
    if not agents:
        agents = ["frontend"]

    tasks: list[BuildTask] = []
    for agent in agents:
        node_id = agent if agent != "tester" else "tester"
        instruction = (
            f"Correção pós-review da spec '{spec_name or 'ativa'}'. "
            f"Resolva APENAS estes problemas:\n{joined}\n\n"
            "Leia get_spec, inspecione arquivos afetados, corrija com edit_file/write_file. "
            "Não reescreva o projeto inteiro."
        )
        if agent == "frontend":
            instruction += f"\nSe existir, leia `{HANDOFF_API_PATH}` antes de integrar com a API."
        tasks.append(
            BuildTask(
                agent=agent,
                node_id=node_id,
                instruction=instruction,
                acceptance="Problemas do review corrigidos",
            )
        )
    return _assign_phases(tasks)


def _task_instruction(
    agent: str,
    node_id: str,
    focus: str,
    acceptance: str,
    stack_hint: str,
) -> str:
    base = (
        f"Implemente no nó '{node_id}' do grafo do projeto. Foco: {focus}. "
        f"Critérios de aceite: {acceptance} "
        "Use get_spec, read_file, edit_file/write_file. "
        "Ao gravar arquivos, chame graph_assign_file com node_id e path."
        f"{stack_hint}"
    )
    if agent == "backend":
        base += (
            f"\nApós implementar endpoints, documente contrato REST em `{HANDOFF_API_PATH}` "
            "(métodos, paths, payloads JSON, exemplos). Crie o diretório se necessário."
        )
    if agent == "frontend":
        base += (
            f"\nAntes de integrar com API, leia `{HANDOFF_API_PATH}` se o arquivo existir."
        )
    return base


def _maybe_dynamic(graph: ProjectGraph, parent: str, labels: list[str]) -> None:
    if len(labels) >= 3:
        graph.maybe_cluster_labels(parent, labels)


def _extract_bullets(body: str, *keywords: str) -> list[str]:
    labels: list[str] = []
    for line in body.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if any(k in lower for k in keywords):
            labels.append(stripped[:80])
    return labels[:8]
