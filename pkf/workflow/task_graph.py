"""Schema e utilitários para DAG de tarefas de build (depends_on)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pkf.workflow.planner import BuildTask

DAG_FORMAT = "dag_v1"


@dataclass
class TaskGraphNode:
    task_id: str
    agent: str
    node_id: str
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"
    title: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent": self.agent,
            "node_id": self.node_id,
            "depends_on": list(self.depends_on),
            "status": self.status,
            "title": self.title or self.agent,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaskGraphNode:
        return cls(
            task_id=str(data["task_id"]),
            agent=str(data.get("agent") or data["task_id"]),
            node_id=str(data.get("node_id") or data["task_id"]),
            depends_on=[str(x) for x in data.get("depends_on") or []],
            status=str(data.get("status") or "pending"),
            title=str(data.get("title") or ""),
        )


def dag_payload_from_tasks(tasks: list[BuildTask]) -> dict:
    return {
        "format": DAG_FORMAT,
        "nodes": [
            TaskGraphNode(
                task_id=t.task_id,
                agent=t.agent,
                node_id=t.node_id,
                depends_on=list(t.depends_on),
            ).to_dict()
            for t in tasks
        ],
    }


def topological_layers(tasks: list[BuildTask]) -> list[list[BuildTask]]:
    """Agrupa tarefas em camadas por ordenação topológica (Kahn)."""
    if not tasks:
        return []
    by_id = {t.task_id: t for t in tasks}
    indegree = {t.task_id: 0 for t in tasks}
    for task in tasks:
        for dep in task.depends_on:
            if dep in by_id:
                indegree[task.task_id] += 1
    layers: list[list[BuildTask]] = []
    remaining = set(by_id)
    while remaining:
        layer = [by_id[tid] for tid in remaining if indegree[tid] == 0]
        if not layer:
            raise ValueError("Ciclo detectado no DAG de tarefas")
        layers.append(layer)
        for task in layer:
            remaining.remove(task.task_id)
            for other in remaining:
                if task.task_id in by_id[other].depends_on:
                    indegree[other] -= 1
    return layers


def ready_tasks(tasks: list[BuildTask], completed: set[str]) -> list[BuildTask]:
    """Tarefas cujo depends_on está totalmente em ``completed``."""
    ready: list[BuildTask] = []
    done = set(completed)
    for task in tasks:
        if task.task_id in done:
            continue
        if all(dep in done for dep in task.depends_on):
            ready.append(task)
    return ready
