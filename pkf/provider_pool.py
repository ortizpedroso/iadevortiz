from __future__ import annotations

import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from pkf.config import ProviderConfig, provider_pool_names
from pkf.providers import get_ai_client


@dataclass
class ProviderPool:
    names: list[str] = field(default_factory=provider_pool_names)
    _index: int = 0
    _cooldown_until: dict[str, float] = field(default_factory=dict)
    _start: str | None = None

    def __post_init__(self) -> None:
        if not self.names:
            raise ValueError(
                "Nenhum provedor configurado. Defina chaves no .env ou PKF_PROVIDER_POOL=groq,gemini,kimi"
            )
        if self._start and self._start in self.names:
            self._index = self.names.index(self._start)

    @classmethod
    def create(cls, start: str | None = None) -> "ProviderPool":
        return cls(_start=start)

    @property
    def current_name(self) -> str:
        return self.names[self._index]

    def mark_cooldown(self, name: str, seconds: int = 1800) -> None:
        self._cooldown_until[name] = time.time() + seconds

    def rotate(self, reason: str = "", cooldown_seconds: int = 0) -> bool:
        if cooldown_seconds:
            self.mark_cooldown(self.current_name, cooldown_seconds)
        if len(self.names) <= 1:
            return False
        start = self._index
        now = time.time()
        for _ in range(len(self.names)):
            self._index = (self._index + 1) % len(self.names)
            name = self.names[self._index]
            if self._cooldown_until.get(name, 0) <= now:
                print(f"[Pool] Provedor → {name} ({reason[:100]})")
                return True
        self._index = start
        return False

    def get_client(self, name: str | None = None) -> tuple[AsyncOpenAI, ProviderConfig]:
        target = name or self.current_name
        if target not in self.names:
            target = self.current_name
        client, config = get_ai_client(target)
        if name:
            self._index = self.names.index(target)
        return client, config

    def status(self) -> dict:
        now = time.time()
        return {
            "current": self.current_name,
            "pool": self.names,
            "cooldown": {
                name: max(0, int(until - now))
                for name, until in self._cooldown_until.items()
                if until > now
            },
        }
