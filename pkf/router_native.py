from __future__ import annotations

import os

TIER_ORDER = ("subscription", "cheap", "free")

_PROVIDER_KEY_ENV: dict[str, tuple[str, ...]] = {
    "groq": ("GROQ_API_KEY", "GROQ_API_KEYS"),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEYS"),
    "kimi": ("MOONSHOT_API_KEY", "KIMI_API_KEY", "MOONSHOT_API_KEYS"),
    "mimo": ("MIMO_API_KEY", "MIMO_API_KEYS"),
    "openai": ("OPENAI_API_KEY", "OPENAI_API_KEYS"),
    "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEYS"),
    "ollama": ("OLLAMA_API_KEY",),
}


def tier_order() -> tuple[str, ...]:
    raw = os.getenv("PKF_PROVIDER_TIERS", "").strip()
    if not raw:
        return TIER_ORDER
    ordered = [part.strip().lower() for part in raw.split(",") if part.strip()]
    return tuple(ordered) if ordered else TIER_ORDER


def collect_api_keys(provider: str) -> list[str]:
    keys: list[str] = []
    for env_name in _PROVIDER_KEY_ENV.get(provider, (f"{provider.upper()}_API_KEY",)):
        value = os.getenv(env_name, "").strip()
        if not value:
            continue
        if env_name.endswith("_API_KEYS"):
            keys.extend(part.strip() for part in value.split(",") if part.strip())
            continue
        if value not in keys:
            keys.append(value)

    prefix = provider.upper()
    index = 2
    while True:
        extra = os.getenv(f"{prefix}_API_KEY_{index}", "").strip()
        if not extra:
            break
        if extra not in keys:
            keys.append(extra)
        index += 1
    return keys


def _providers_with_keys() -> list[str]:
    from pkf.config import providers

    names: list[str] = []
    for name, cfg in providers().items():
        if name == "ollama":
            names.append(name)
            continue
        if collect_api_keys(name) or cfg.api_key:
            names.append(name)
    return names


def _tier_provider_names(tier: str) -> list[str]:
    explicit = os.getenv(f"PKF_TIER_{tier.upper()}", "").strip()
    if explicit:
        return [part.strip() for part in explicit.split(",") if part.strip()]

    available = _providers_with_keys()
    if tier == "subscription":
        primary = os.getenv("PKF_PROVIDER", "").strip()
        if primary and primary in available:
            return [primary]
        return [name for name in ("groq", "deepseek", "kimi", "openai") if name in available]
    if tier == "cheap":
        return [name for name in ("gemini", "deepseek", "mimo") if name in available]
    return [name for name in ("groq", "gemini") if name in available]


def _model_for_tier(provider: str, tier: str) -> str | None:
    override = os.getenv(f"PKF_{provider.upper()}_{tier.upper()}_MODEL", "").strip()
    if override:
        return override
    if tier == "free" and provider == "groq":
        free_model = os.getenv("PKF_GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant").strip()
        return free_model or None
    return None


def _ninerouter_slot() -> dict | None:
    from pkf.ninerouter import (
        ninerouter_api_key,
        ninerouter_chat_model,
        ninerouter_enabled,
        ninerouter_should_skip,
    )

    if not ninerouter_enabled():
        return None
    skip, _reason = ninerouter_should_skip()
    if skip:
        return None
    return {
        "slot_id": "ninerouter#0",
        "provider": "ninerouter",
        "api_key": ninerouter_api_key(),
        "tier": "subscription",
        "model": ninerouter_chat_model(),
    }


def _quality_slot() -> dict | None:
    from pkf.config import providers as provider_catalog
    from pkf.config import quality_tier_model, quality_tier_provider

    provider = quality_tier_provider()
    if not provider:
        return None
    catalog = provider_catalog()
    if provider not in catalog:
        return None
    if provider == "ninerouter":
        from pkf.ninerouter import ninerouter_api_key, ninerouter_should_skip

        if ninerouter_should_skip()[0]:
            return None
        api_key = ninerouter_api_key() or "local"
        model = quality_tier_model() or catalog[provider].model
        return {
            "slot_id": "ninerouter#quality",
            "provider": "ninerouter",
            "api_key": api_key,
            "tier": "quality",
            "model": model,
        }
    keys = collect_api_keys(provider)
    if not keys and catalog[provider].api_key:
        keys = [catalog[provider].api_key]
    if not keys:
        return None
    model = quality_tier_model() or catalog[provider].model
    return {
        "slot_id": f"{provider}#quality",
        "provider": provider,
        "api_key": keys[0],
        "tier": "quality",
        "model": model,
    }


def build_provider_slots() -> list[dict]:
    from pkf.config import provider_pool_names, providers

    catalog = providers()
    slots: list[dict] = []
    gateway = _ninerouter_slot()
    if gateway:
        slots.append(gateway)
    quality = _quality_slot()
    if quality:
        slots.append(quality)
    for tier in tier_order():
        for provider in _tier_provider_names(tier):
            if provider in {"ninerouter", "9router"}:
                continue
            if provider not in catalog:
                continue
            keys = collect_api_keys(provider)
            if not keys and catalog[provider].api_key:
                keys = [catalog[provider].api_key]
            if not keys and provider != "ollama":
                continue
            if not keys:
                keys = ["ollama"]
            for index, api_key in enumerate(keys):
                slots.append(
                    {
                        "slot_id": f"{provider}#{index}",
                        "provider": provider,
                        "api_key": api_key,
                        "tier": tier,
                        "model": _model_for_tier(provider, tier),
                    }
                )

    if slots:
        return _dedupe_slots(slots)

    for provider in provider_pool_names():
        if provider not in catalog:
            continue
        keys = collect_api_keys(provider) or ([catalog[provider].api_key] if catalog[provider].api_key else [])
        for index, api_key in enumerate(keys):
            slots.append(
                {
                    "slot_id": f"{provider}#{index}",
                    "provider": provider,
                    "api_key": api_key,
                    "tier": "subscription",
                    "model": None,
                }
            )
    return _dedupe_slots(slots)


def _dedupe_slots(slots: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for slot in slots:
        fingerprint = (slot["provider"], slot["api_key"], slot["tier"])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(slot)
    return unique
