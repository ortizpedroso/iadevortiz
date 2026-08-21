from __future__ import annotations

import json
import re
from pathlib import Path

import networkx as nx

from pkf.config import MEMORY_DOMAIN_STOPWORDS, MEMORY_MIN_OVERLAP_WORDS, pkf_dir


def _memory_tokens(text: str) -> set[str]:
    words = {word for word in re.findall(r"[a-zà-ú0-9]+", text.lower()) if len(word) > 3}
    return {word for word in words if word not in MEMORY_DOMAIN_STOPWORDS}


def _memory_match_score(user_words: set[str], summary_words: set[str]) -> tuple[int, float]:
    if not user_words:
        return 0, 0.0
    overlap = user_words & summary_words
    ratio = len(overlap) / len(user_words)
    return len(overlap), ratio


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

    def find(self, user_input: str, threshold: float) -> tuple[str | None, int]:
        if not self.index:
            return None, 0
        user_words = _memory_tokens(user_input)
        if not user_words:
            return None, 0
        best_name = None
        best_overlap = 0
        best_ratio = 0.0
        for name, summary in self.index.items():
            overlap, ratio = _memory_match_score(user_words, _memory_tokens(summary))
            if ratio > best_ratio or (ratio == best_ratio and overlap > best_overlap):
                best_overlap = overlap
                best_ratio = ratio
                best_name = name
        if best_ratio >= threshold and best_overlap >= MEMORY_MIN_OVERLAP_WORDS:
            return best_name, int(round(best_ratio * 100))
        return None, int(round(best_ratio * 100))


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
