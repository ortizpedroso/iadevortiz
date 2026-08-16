from pkf.config import default_provider, provider_pool_names, providers
from pkf.ninerouter import ninerouter_api_key, ninerouter_chat_model, ninerouter_enabled, ninerouter_web_search
from pkf.router_native import build_provider_slots
from pkf.web_search import web_search, web_search_configured


def test_default_provider_prefers_ninerouter(monkeypatch):
    monkeypatch.setenv("PKF_ENV", "production")
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    assert default_provider() == "ninerouter"


def test_provider_pool_puts_ninerouter_first(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("PKF_PROVIDER_POOL", raising=False)
    names = provider_pool_names()
    assert names[0] == "ninerouter"
    assert "groq" in names


def test_build_slots_ninerouter_first(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("PKF_TIER_SUBSCRIPTION", "groq")
    slots = build_provider_slots()
    assert slots[0]["provider"] == "ninerouter"
    assert any(slot["provider"] == "groq" for slot in slots)


def test_ninerouter_provider_registered(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("NINEROUTER_MODEL", "kr/claude-sonnet-4.5")
    cfg = providers()["ninerouter"]
    assert cfg.base_url.endswith("/v1")
    assert cfg.model == "kr/claude-sonnet-4.5"


def test_ninerouter_model_default(monkeypatch):
    monkeypatch.delenv("NINEROUTER_MODEL", raising=False)
    monkeypatch.delenv("PKF_NINEROUTER_MODEL", raising=False)
    assert ninerouter_chat_model() == "oc/big-pickle"


def test_web_search_configured_with_ninerouter(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert web_search_configured()
    assert ninerouter_enabled()


def test_web_search_requires_backend(monkeypatch):
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    assert "indisponível" in web_search("python fastapi").lower()


def test_ninerouter_web_search_requires_url(monkeypatch):
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    assert "não configurado" in ninerouter_web_search("test").lower()


def test_ninerouter_api_key_not_local_by_default(monkeypatch):
    monkeypatch.delenv("NINEROUTER_KEY", raising=False)
    monkeypatch.delenv("NINEROUTER_API_KEY", raising=False)
    assert ninerouter_api_key() == ""
