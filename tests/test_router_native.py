from pkf.provider_pool import ProviderPool
from pkf.router_native import build_provider_slots, collect_api_keys, tier_order
from pkf.web_search import web_search, web_search_configured


def test_collect_multiple_groq_keys(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "key-a")
    monkeypatch.setenv("GROQ_API_KEY_2", "key-b")
    keys = collect_api_keys("groq")
    assert keys == ["key-a", "key-b"]


def test_build_slots_with_tiers(monkeypatch):
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "g1")
    monkeypatch.setenv("GEMINI_API_KEY", "gem")
    monkeypatch.setenv("PKF_TIER_SUBSCRIPTION", "groq")
    monkeypatch.setenv("PKF_TIER_CHEAP", "gemini")
    monkeypatch.delenv("PKF_TIER_FREE", raising=False)
    slots = build_provider_slots()
    tiers = [slot["tier"] for slot in slots]
    assert "subscription" in tiers
    assert "cheap" in tiers
    assert any(slot["provider"] == "groq" for slot in slots)


def test_pool_rotates_within_tier(monkeypatch):
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "g1")
    monkeypatch.setenv("GROQ_API_KEY_2", "g2")
    monkeypatch.setenv("PKF_PROVIDER_TIERS", "subscription")
    monkeypatch.setenv("PKF_TIER_SUBSCRIPTION", "groq")
    pool = ProviderPool()
    assert pool.current_slot.slot_id == "groq#0"
    assert pool.rotate()
    assert pool.current_slot.slot_id == "groq#1"


def test_pool_escalates_tier(monkeypatch):
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "g1")
    monkeypatch.setenv("GEMINI_API_KEY", "gem")
    monkeypatch.setenv("PKF_PROVIDER_TIERS", "subscription,cheap")
    monkeypatch.setenv("PKF_TIER_SUBSCRIPTION", "groq")
    monkeypatch.setenv("PKF_TIER_CHEAP", "gemini")
    pool = ProviderPool()
    pool.mark_cooldown(pool.current_slot.slot_id, 3600)
    assert pool.rotate()
    assert pool.current_slot.tier == "cheap"
    assert pool.current_slot.provider == "gemini"


def test_web_search_requires_key(monkeypatch):
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    assert "indisponível" in web_search("python fastapi").lower()
    assert not web_search_configured()


def test_tier_order_custom(monkeypatch):
    monkeypatch.setenv("PKF_PROVIDER_TIERS", "cheap,free")
    assert tier_order() == ("cheap", "free")
