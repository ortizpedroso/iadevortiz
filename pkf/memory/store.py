from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from pkf.config import pkf_dir


class MemoryStore:
    def __init__(self, workspace_root: Path):
        self.path = pkf_dir(workspace_root) / "memory" / "index.json"
        self.index: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.index = {str(k): str(v) for k, v in data.items()}
            except json.JSONDecodeError:
                self.index = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.index, ensure_ascii=False, indent=2), encoding="utf-8")

    def register(self, name: str, summary: str) -> None:
        self.index[name] = summary
        self.save()

    def find(self, user_input: str, threshold: int) -> tuple[str | None, int]:
        if not self.index:
            return None, 0
        words = {word for word in user_input.lower().split() if len(word) > 3}
        best_name = None
        best_score = 0
        for name, summary in self.index.items():
            summary_words = {word for word in summary.lower().split() if len(word) > 3}
            score = len(words & summary_words)
            if score > best_score:
                best_score = score
                best_name = name
        if best_score >= threshold:
            return best_name, best_score
        return None, best_score


def export_graph(graph: nx.DiGraph, dest: Path) -> str:
    if graph.number_of_nodes() == 0:
        return "Grafo vazio; nada para salvar."
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        dest.with_suffix(".json").write_text(
            json.dumps(nx.node_link_data(graph), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return f"matplotlib ausente; grafo salvo em {dest.with_suffix('.json')}"
    pos = nx.spring_layout(graph, seed=7)
    plt.figure(figsize=(10, 7))
    nx.draw(graph, pos, with_labels=True, node_size=700, font_size=8)
    plt.tight_layout()
    plt.savefig(dest)
    plt.close()
    return f"Grafo salvo em {dest}"
