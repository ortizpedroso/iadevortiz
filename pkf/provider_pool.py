from __future__ import annotations

import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from pkf.config import ProviderConfig
from pkf.providers import get_ai_client
from pkf.router_native import build_provider_slots, tier_order


@dataclass(frozen=True)
class ProviderSlot:
    slot_id: str
    provider: str
    api_key: str
    tier: str
    model: str | None = None


def _load_slots(raw: list[dict] | None = None) -> list[ProviderSlot]:
    source = raw if raw is not None else build_provider_slots()
    return [
        ProviderSlot(
            slot_id=item["slot_id"],
            provider=item["provider"],
            api_key=item["api_key"],
            tier=item["tier"],
            model=item.get("model"),
        )
        for item in source
    ]


@dataclass
class ProviderPool:
    slots: list[ProviderSlot] = field(default_factory=_load_slots)
    _index: int = 0
    _cooldown_until: dict[str, float] = field(default_factory=dict)
    _start: str | None = None

    def __post_init__(self) -> None:
        if not self.slots:
            raise ValueError(
                "Nenhum provedor configurado. Defina chaves no .env ou PKF_PROVIDER_POOL=groq,gemini,kimi"
            )
        if self._start:
            for index, slot in enumerate(self.slots):
                if slot.provider == self._start:
                    self._index = index
                    break

    @classmethod
    def create(cls, start: str | None = None) -> "ProviderPool":
        return cls(_start=start)

    @property
    def current_slot(self) -> ProviderSlot:
        return self.slots[self._index]

    @property
    def current_name(self) -> str:
        return self.current_slot.provider

    @property
    def names(self) -> list[str]:
        seen: list[str] = []
        for slot in self.slots:
            if slot.provider not in seen:
                seen.append(slot.provider)
        return seen

    def mark_cooldown(self, slot_id: str, seconds: int = 1800) -> None:
        self._cooldown_until[slot_id] = time.time() + seconds

    def _slot_available(self, slot: ProviderSlot, now: float) -> bool:
        return self._cooldown_until.get(slot.slot_id, 0) <= now

    def rotate(self, reason: str = "", cooldown_seconds: int = 0) -> bool:
        if cooldown_seconds:
            self.mark_cooldown(self.current_slot.slot_id, cooldown_seconds)
        if len(self.slots) <= 1:
            return False

        now = time.time()
        start = self._index
        current_tier = self.current_slot.tier

        for _ in range(len(self.slots)):
            self._index = (self._index + 1) % len(self.slots)
            slot = self.slots[self._index]
            if slot.tier == current_tier and self._slot_available(slot, now):
                print(f"[Pool] {slot.tier}/{slot.slot_id} → {slot.provider} ({reason[:80]})")
                return True

        tiers = tier_order()
        if current_tier in tiers:
            start_tier = tiers.index(current_tier) + 1
        else:
            start_tier = 0
        for tier in tiers[start_tier:]:
            for index, slot in enumerate(self.slots):
                if slot.tier == tier and self._slot_available(slot, now):
                    self._index = index
                    print(f"[Pool] tier ↑ {tier} → {slot.slot_id} ({reason[:80]})")
                    return True

        self._index = start
        return False

    def get_client(self, name: str | None = None) -> tuple[AsyncOpenAI, ProviderConfig]:
        if name:
            for index, slot in enumerate(self.slots):
                if slot.provider == name:
                    self._index = index
                    break
        slot = self.current_slot
        return get_ai_client(slot.provider, api_key=slot.api_key, model=slot.model)

    def status(self) -> dict:
        now = time.time()
        return {
            "current": self.current_name,
            "slot": self.current_slot.slot_id,
            "tier": self.current_slot.tier,
            "model": self.current_slot.model,
            "pool": self.names,
            "tiers": list(tier_order()),
            "slots": [
                {
                    "slot_id": slot.slot_id,
                    "provider": slot.provider,
                    "tier": slot.tier,
                    "model": slot.model,
                    "cooldown_sec": max(0, int(self._cooldown_until.get(slot.slot_id, 0) - now)),
                }
                for slot in self.slots
            ],
            "cooldown": {
                slot_id: max(0, int(until - now))
                for slot_id, until in self._cooldown_until.items()
                if until > now
            },
        }
