from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pkf.config import pkf_dir

MEMORY_FILE = "MEMORY.md"
CHECKPOINT_FILE = "checkpoint.md"
DEFAULT_BUDGETS = {
    "memory": 4000,
    "checkpoint": 3500,
    "tasks": 2000,
}


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n…(truncado)"


def ensure_memory_files(workspace_root: Path) -> None:
    root = pkf_dir(workspace_root)
    memory = root / MEMORY_FILE
    checkpoint = root / CHECKPOINT_FILE
    if not memory.exists():
        memory.write_text(
            "# Memória do projeto\n\nRegras, stack e decisões persistentes.\n",
            encoding="utf-8",
        )
    if not checkpoint.exists():
        checkpoint.write_text(
            "# Checkpoint da sessão\n\nEstado atual da implementação.\n",
            encoding="utf-8",
        )


def read_memory_context(workspace_root: Path, budgets: dict | None = None) -> str:
    ensure_memory_files(workspace_root)
    caps = {**DEFAULT_BUDGETS, **(budgets or {})}
    root = pkf_dir(workspace_root)
    parts: list[str] = []

    memory = (root / MEMORY_FILE).read_text(encoding="utf-8").strip()
    if memory:
        parts.append("[Memória do projeto]\n" + _truncate(memory, caps["memory"]))

    checkpoint = (root / CHECKPOINT_FILE).read_text(encoding="utf-8").strip()
    if checkpoint:
        parts.append("[Checkpoint da sessão]\n" + _truncate(checkpoint, caps["checkpoint"]))

    tasks_dir = root / "tasks"
    if tasks_dir.is_dir():
        progress_blocks: list[str] = []
        for path in sorted(tasks_dir.glob("*/progress.md")):
            text = path.read_text(encoding="utf-8").strip()
            if text:
                progress_blocks.append(f"## {path.parent.name}\n{text}")
        if progress_blocks:
            joined = "\n\n".join(progress_blocks)
            parts.append("[Progresso de tarefas]\n" + _truncate(joined, caps["tasks"]))

    return "\n\n".join(parts)


def write_checkpoint(workspace_root: Path, phase: str, spec: str | None, note: str = "") -> None:
    ensure_memory_files(workspace_root)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    body = (
        f"# Checkpoint da sessão\n\n"
        f"- Atualizado: {stamp}\n"
        f"- Fase: {phase}\n"
        f"- Spec: {spec or '(nenhuma)'}\n\n"
    )
    if note:
        body += f"## Estado\n{note.strip()}\n"
    (pkf_dir(workspace_root) / CHECKPOINT_FILE).write_text(body, encoding="utf-8")


def append_memory_note(workspace_root: Path, section: str, text: str) -> None:
    ensure_memory_files(workspace_root)
    path = pkf_dir(workspace_root) / MEMORY_FILE
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    block = f"\n\n## {section} ({stamp})\n{text.strip()}\n"
    path.write_text(path.read_text(encoding="utf-8").rstrip() + block, encoding="utf-8")


def task_progress_path(workspace_root: Path, task_id: str) -> Path:
    path = pkf_dir(workspace_root) / "tasks" / task_id
    path.mkdir(parents=True, exist_ok=True)
    return path / "progress.md"
