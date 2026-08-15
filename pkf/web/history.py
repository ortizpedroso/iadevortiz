from __future__ import annotations

import json
from pathlib import Path

from pkf.config import pkf_dir


class ChatHistory:
    def __init__(self, workspace_root: Path):
        self.path = pkf_dir(workspace_root) / "chats" / "current.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.messages: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def save(self) -> None:
        self.path.write_text(json.dumps(self.messages, ensure_ascii=False, indent=2), encoding="utf-8")

    def append(self, message: dict) -> None:
        self.messages.append(message)
        self.save()

    def clear(self) -> None:
        self.messages = []
        self.save()
