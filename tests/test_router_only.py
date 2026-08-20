"""Modo PKF_ROUTER_ONLY — gateway OmniRoute exclusivo."""

from pkf.config import default_provider, provider_pool_names, router_only_mode
from pkf.judge import _judge_client
from pkf.ninerouter import ninerouter_auth_warning
from pkf.router_native import build_provider_slots


def _mock_ninerouter_ok(monkeypatch):
    monkeypatch.setenv("NINEROUTER_KEY", "sk-test")
    monkeypatch.setattr("pkf.ninerouter.ninerouter_health", lambda: (True, "ok"))


def test_router_only_flag(monkeypatch):
    monkeypatch.delenv("PKF_ROUTER_ONLY", raising=False)
    assert router_only_mode() is False
    monkeypatch.setenv("PKF_ROUTER_ONLY", "1")
    assert router_only_mode() is True


def test_router_only_pool_is_ninerouter_only(monkeypatch):
    monkeypatch.setenv("PKF_ROUTER_ONLY", "1")
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("GEMINI_API_KEY", "gem")
    _mock_ninerouter_ok(monkeypatch)
    assert provider_pool_names() == ["ninerouter"]


def test_router_only_slots_exclude_direct_providers(monkeypatch):
    monkeypatch.setenv("PKF_ROUTER_ONLY", "1")
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("PKF_TIER_SUBSCRIPTION", "groq")
    _mock_ninerouter_ok(monkeypatch)
    slots = build_provider_slots()
    providers_in_slots = {slot["provider"] for slot in slots}
    assert providers_in_slots == {"ninerouter"}


def test_router_only_default_provider(monkeypatch):
    monkeypatch.setenv("PKF_ROUTER_ONLY", "1")
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    _mock_ninerouter_ok(monkeypatch)
    assert default_provider() == "ninerouter"


def test_router_only_no_groq_fallback_on_missing_key(monkeypatch):
    monkeypatch.setenv("PKF_ROUTER_ONLY", "1")
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("NINEROUTER_KEY", raising=False)
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    assert default_provider() == "ninerouter"
    assert provider_pool_names() == ["ninerouter"]
    slots = build_provider_slots()
    assert slots and slots[0]["provider"] == "ninerouter"
    from pkf.provider_pool import ProviderPool

    pool = ProviderPool.create(start="ninerouter")
    assert pool.current_name == "ninerouter"


def test_router_only_auth_warning(monkeypatch):
    monkeypatch.setenv("PKF_ROUTER_ONLY", "1")
    text = ninerouter_auth_warning("401")
    assert "OmniRoute" in text
    assert "router-only" in text
    assert "Gemini/Groq" not in text


def test_judge_uses_ninerouter_in_router_only(monkeypatch):
    monkeypatch.setenv("PKF_ROUTER_ONLY", "1")
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("NINEROUTER_KEY", "sk-test")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    _client, model = _judge_client("ninerouter")
    assert model
