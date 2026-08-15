from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pkf.config import pkf_dir
from pkf.workspace_index import _lock_for

PREDEFINED_NODES: dict[str, str] = {
    "spec": "architect",
    "frontend": "frontend",
    "backend": "backend",
    "database": "backend",
    "auth": "backend",
    "logic": "logic",
    "tests": "tester",
    "devops": "backend",
}

MIN_LABELS_FOR_DYNAMIC = 3


@dataclass
class GraphNode:
    id: str
    agent: str
    kind: str = "predefined"
    parent: str | None = None
    status: str = "idle"
    labels: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


class ProjectGraph:
    def __init__(self, root: Path):
        self.root = root
        self.path = pkf_dir(root) / "graph" / "project.json"
        self.nodes: dict[str, GraphNode] = {}
        self._load()

    def _load(self) -> None:
        self.ensure_predefined()
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        for item in data.get("nodes", []):
            node = GraphNode(**item)
            self.nodes[node.id] = node
        self.ensure_predefined()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"nodes": [asdict(n) for n in self.nodes.values()]}
        with _lock_for(self.root):
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def ensure_predefined(self) -> None:
        for node_id, agent in PREDEFINED_NODES.items():
            if node_id not in self.nodes:
                self.nodes[node_id] = GraphNode(id=node_id, agent=agent, kind="predefined")

    def add_dynamic_node(self, node_id: str, parent: str, labels: list[str]) -> GraphNode | None:
        if len(labels) < MIN_LABELS_FOR_DYNAMIC:
            return None
        slug = _slug(node_id)
        parent_node = self.nodes.get(parent)
        agent = parent_node.agent if parent_node else "frontend"
        node = GraphNode(
            id=slug,
            agent=agent,
            kind="dynamic",
            parent=parent,
            labels=labels,
        )
        self.nodes[slug] = node
        self.save()
        return node

    def maybe_cluster_labels(self, parent: str, labels: list[str]) -> GraphNode | None:
        clean = [label.strip() for label in labels if label.strip()]
        if len(clean) < MIN_LABELS_FOR_DYNAMIC:
            return None
        name = _slug("-".join(clean[:2]))
        if name in self.nodes:
            existing = self.nodes[name]
            existing.labels = list(dict.fromkeys(existing.labels + clean))
            self.save()
            return existing
        return self.add_dynamic_node(name, parent, clean)

    def assign_file(self, node_id: str, file_path: str) -> None:
        with _lock_for(self.root):
            self._load()
            node = self.nodes.get(node_id)
            if not node:
                return
            rel = file_path.replace("\\", "/")
            if rel not in node.files:
                node.files.append(rel)
                node.status = "working"
                self.save()

    def set_status(self, node_id: str, status: str) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].status = status
            self.save()

    def nodes_for_agent(self, agent: str) -> list[GraphNode]:
        return [n for n in self.nodes.values() if n.agent == agent]

    def summary(self) -> str:
        lines = ["Grafo do projeto:"]
        for node in sorted(self.nodes.values(), key=lambda n: n.id):
            files = ", ".join(node.files[:5]) or "(sem arquivos)"
            lines.append(f"- {node.id} [{node.kind}] agent={node.agent} status={node.status} files={files}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"nodes": [asdict(n) for n in self.nodes.values()]}


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip().lower()).strip("-")
    return cleaned or "node"
