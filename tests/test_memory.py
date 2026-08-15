from pathlib import Path

from pkf.config import RELEVANCE_THRESHOLD
from pkf.memory.store import MemoryStore


def test_memory_register_and_find(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.register("memoria_frontend_1-12", "decisão de usar react no botão da tela de login")
    name, score = store.find("como ficou o botão da tela de login?", RELEVANCE_THRESHOLD)
    assert name == "memoria_frontend_1-12"
    assert score >= RELEVANCE_THRESHOLD
