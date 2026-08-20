"""Tier de qualidade (Claude via gateway) — só architect e reviewer."""


from pkf.config import (
    QUALITY_TIER_AGENTS,
    agent_uses_quality_tier,
    quality_tier_provider,
)
from pkf.provider_pool import ProviderPool
from pkf.router_native import build_provider_slots


def _mock_ninerouter_ok(monkeypatch):
    monkeypatch.setenv("NINEROUTER_KEY", "sk-test")
    monkeypatch.setattr("pkf.ninerouter.ninerouter_health", lambda: (True, "ok"))


def test_quality_slot_created_for_ninerouter(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("PKF_TIER_QUALITY", "ninerouter")
    monkeypatch.setenv("PKF_QUALITY_MODEL", "kr/claude-sonnet-4.5")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    _mock_ninerouter_ok(monkeypatch)
    slots = build_provider_slots()
    quality = [s for s in slots if s.get("tier") == "quality"]
    assert len(quality) == 1
    assert quality[0]["provider"] == "ninerouter"
    assert quality[0]["model"] == "kr/claude-sonnet-4.5"


def test_architect_uses_quality_tier(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("PKF_TIER_QUALITY", "ninerouter")
    monkeypatch.setenv("PKF_QUALITY_MODEL", "kr/claude-sonnet-4.5")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("PKF_TIER_SUBSCRIPTION", "groq")
    _mock_ninerouter_ok(monkeypatch)
    pool = ProviderPool()
    _, config = pool.get_client_for_agent("architect")
    assert config.model == "kr/claude-sonnet-4.5"


def test_frontend_never_uses_quality_tier(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("PKF_TIER_QUALITY", "ninerouter")
    monkeypatch.setenv("PKF_QUALITY_MODEL", "kr/claude-sonnet-4.5")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("PKF_TIER_SUBSCRIPTION", "groq")
    _mock_ninerouter_ok(monkeypatch)
    pool = ProviderPool()
    _, config = pool.get_client_for_agent("frontend")
    assert config.model != "kr/claude-sonnet-4.5"
    assert pool.current_slot.tier != "quality"


def test_without_quality_config_unchanged(monkeypatch):
    monkeypatch.delenv("PKF_TIER_QUALITY", raising=False)
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "g")
    assert not agent_uses_quality_tier("architect")
    slots = build_provider_slots()
    assert not any(s.get("tier") == "quality" for s in slots)


def test_quality_agents_set():
    assert frozenset({"architect", "reviewer"}) == QUALITY_TIER_AGENTS
    assert quality_tier_provider() is None or isinstance(quality_tier_provider(), str)
