from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pkf.config import pkf_dir
from pkf.db.config import database_enabled

_TASK_LABELS = {
    "frontend": "Frontend",
    "backend": "Backend",
    "logic": "Lógica",
    "tester": "Testes",
}

_TITLE_TO_AGENT = {
    "frontend": "frontend",
    "backend": "backend",
    "lógica": "logic",
    "logica": "logic",
    "testes": "tester",
}


@dataclass
class TaskNode:
    id: str
    title: str
    status: str = "pending"
    detail: str = ""
    children: list[TaskNode] = field(default_factory=list)

    def to_dict(self) -> dict:
        out = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "children": [c.to_dict() for c in self.children],
        }
        if self.detail:
            out["detail"] = self.detail
        return out


class TaskTracker:
    def __init__(self, workspace_root: Path, db_context=None):
        self.root = workspace_root
        self.path = pkf_dir(workspace_root) / "tasks.json"
        self.db = db_context
        self.tree: TaskNode | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.tree = None
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.tree = _node_from_dict(data)
        except (json.JSONDecodeError, KeyError):
            self.tree = None

    def persist(self) -> None:
        if not self.tree:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.tree.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if database_enabled() and self.db:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.db.save_tasks([self.tree.to_dict()]))  # noqa: RUF006
            except RuntimeError:
                pass

    async def persist_async(self) -> None:
        self.persist()
        if database_enabled() and self.db and self.tree:
            await self.db.setup()
            await self.db.save_tasks([self.tree.to_dict()])

    def _agent_from_child_title(self, title: str) -> str | None:
        lower = title.lower()
        for prefix, agent in _TITLE_TO_AGENT.items():
            if lower.startswith(prefix):
                return agent
        return None

    def agent_statuses(self) -> dict[str, str]:
        """Mapa agente → status na fase T2 (implementação)."""
        if not self.tree:
            return {}
        impl = next((c for c in self.tree.children if c.id == "T2"), None)
        if not impl:
            return {}
        out: dict[str, str] = {}
        for child in impl.children:
            agent = self._agent_from_child_title(child.title)
            if agent:
                out[agent] = child.status
        return out

    def done_agents(self) -> set[str]:
        return {agent for agent, status in self.agent_statuses().items() if status == "done"}

    def prepare_for_build(self, spec_name: str | None, agents: list[str], *, resume: bool = False) -> set[str]:
        """Inicializa ou retoma a árvore de tarefas. Retorna agentes já concluídos (para pular)."""
        spec_label = spec_name or "projeto"
        if resume and self.tree:
            spec_node = next((c for c in self.tree.children if c.id == "T1.1"), None)
            if spec_node and spec_node.title == f"Spec: {spec_label}":
                done = self.done_agents()
                statuses = self.agent_statuses()
                impl = next((c for c in self.tree.children if c.id == "T2"), None)
                if impl:
                    existing = {self._agent_from_child_title(c.title): c for c in impl.children}
                    new_children: list[TaskNode] = []
                    for i, agent in enumerate(agents):
                        prev = existing.get(agent)
                        if prev:
                            new_children.append(prev)
                        else:
                            new_children.append(
                                TaskNode(id=f"T2.{i + 1}", title=_agent_label(agent), status="pending")
                            )
                    impl.children = new_children
                    for agent in agents:
                        if statuses.get(agent) == "failed":
                            self.set_child_status(agent, "pending")
                    self.tree.status = "running"
                    impl.status = "running"
                    self.persist()
                    return done
        self.reset_for_build(spec_name, agents)
        return set()

    def reset_for_build(self, spec_name: str | None, agents: list[str]) -> None:
        spec_label = spec_name or "projeto"
        children = [
            TaskNode(id=f"T2.{i + 1}", title=_agent_label(agent), status="pending")
            for i, agent in enumerate(agents)
        ]
        self.tree = TaskNode(
            id="T1",
            title="Build",
            status="running",
            children=[
                TaskNode(id="T1.1", title=f"Spec: {spec_label}", status="done"),
                TaskNode(id="T2", title="Implementação em fases", status="running", children=children),
                TaskNode(id="T3", title="Verificação", status="pending"),
                TaskNode(id="T4", title="Review e correções", status="pending"),
                TaskNode(id="T5", title="Aprovação final", status="pending"),
            ],
        )
        self.persist()

    def set_child_status(self, agent: str, status: str, *, detail: str = "") -> None:
        if not self.tree:
            return
        for child in self._walk(self.tree):
            if child.title.lower().startswith(_agent_label(agent).lower()[:8]):
                child.status = status
                if detail:
                    child.detail = detail
                self._write_progress(child)
        self.persist()

    def set_child_detail(self, agent: str, detail: str) -> None:
        if not self.tree:
            return
        for child in self._walk(self.tree):
            if child.title.lower().startswith(_agent_label(agent).lower()[:8]):
                child.detail = detail
                self._write_progress(child)
        self.persist()

    def mark_resume_agents(self, agents: set[str]) -> None:
        """Marca agentes já concluídos ao retomar build."""
        for agent in agents:
            self.set_child_status(agent, "done", detail="retomado — handoff preservado")

    def set_phase_status(self, phase_id: str, status: str) -> None:
        if not self.tree:
            return
        for node in self._walk(self.tree):
            if node.id == phase_id:
                node.status = status
                self._write_progress(node)
        self.persist()

    def to_list(self) -> list[dict]:
        if not self.tree:
            return []
        return [self.tree.to_dict()]

    def _write_progress(self, node: TaskNode) -> None:
        stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        from pkf.memory.persistent import task_progress_path

        path = task_progress_path(self.root, node.id)
        path.write_text(
            f"# {node.title}\n\n- Status: {node.status}\n- Atualizado: {stamp}\n",
            encoding="utf-8",
        )

    @staticmethod
    def _walk(node: TaskNode) -> list[TaskNode]:
        out = [node]
        for child in node.children:
            out.extend(TaskTracker._walk(child))
        return out


def _agent_label(agent: str) -> str:
    return _TASK_LABELS.get(agent, agent.capitalize())


def _node_from_dict(data: dict) -> TaskNode:
    return TaskNode(
        id=data["id"],
        title=data["title"],
        status=data.get("status", "pending"),
        detail=data.get("detail", ""),
        children=[_node_from_dict(c) for c in data.get("children", [])],
    )
