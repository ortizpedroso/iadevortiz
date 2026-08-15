from __future__ import annotations

from dataclasses import dataclass

from pkf.graph.project import ProjectGraph
from pkf.spec.store import load_spec

FRONTEND_HINTS = ("ui", "interface", "html", "css", "react", "página", "pagina", "tela", "botão", "botao", "layout")
BACKEND_HINTS = ("api", "backend", "servidor", "endpoint", "auth", "banco", "database", "sql", "crud")
LOGIC_HINTS = ("regra", "negócio", "negocio", "algoritmo", "cálculo", "calculo", "whitelabel", "multi-tenant")


@dataclass
class BuildTask:
    agent: str
    node_id: str
    instruction: str
    parallel: bool = True


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

    def add(agent: str, node_id: str, focus: str) -> None:
        stack_hint = ""
        if stack:
            stack_hint = "\nStack confirmada: " + ", ".join(f"{k}={v}" for k, v in stack.items())
        tasks.append(
            BuildTask(
                agent=agent,
                node_id=node_id,
                instruction=(
                    f"Implemente no nó '{node_id}' do grafo do projeto. Foco: {focus}. "
                    "Use get_spec, read_file, edit_file/write_file. "
                    "Ao gravar arquivos, chame graph_assign_file com node_id e path."
                    f"{stack_hint}"
                ),
            )
        )

    if any(h in text for h in FRONTEND_HINTS) or "frontend" in stack:
        add("frontend", "frontend", "interface e assets públicos")
        _maybe_dynamic(graph, "frontend", _extract_bullets(body, "frontend", "ui", "tela"))
    if any(h in text for h in BACKEND_HINTS) or "backend" in stack or "database" in stack:
        add("backend", "backend", "API, persistência e serviços")
        _maybe_dynamic(graph, "backend", _extract_bullets(body, "api", "backend", "banco"))
    if any(h in text for h in LOGIC_HINTS):
        add("logic", "logic", "regras de negócio e whitelabel")
    if not tasks:
        add("frontend", "frontend", "implementação principal da spec")
    return tasks


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
