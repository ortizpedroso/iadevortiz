from pkf.config import default_provider, provider_pool_names, providers
from pkf.ninerouter import (
    is_ninerouter_auth_error,
    ninerouter_api_key,
    ninerouter_auth_warning,
    ninerouter_chat_model,
    ninerouter_enabled,
    ninerouter_should_skip,
    ninerouter_web_search,
)
from pkf.provider_pool import ProviderPool
from pkf.router_native import build_provider_slots
from pkf.web_search import web_search, web_search_configured


def _mock_ninerouter_ok(monkeypatch):
    monkeypatch.setenv("NINEROUTER_KEY", "sk-test")
    monkeypatch.setattr("pkf.ninerouter.ninerouter_health", lambda: (True, "ok"))


def test_default_provider_prefers_ninerouter(monkeypatch):
    monkeypatch.setenv("PKF_ENV", "production")
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    _mock_ninerouter_ok(monkeypatch)
    assert default_provider() == "ninerouter"


def test_provider_pool_puts_ninerouter_first(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    monkeypatch.delenv("PKF_PROVIDER_POOL", raising=False)
    _mock_ninerouter_ok(monkeypatch)
    names = provider_pool_names()
    assert names[0] == "ninerouter"
    assert "groq" in names


def test_build_slots_ninerouter_first(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("PKF_TIER_SUBSCRIPTION", "groq")
    _mock_ninerouter_ok(monkeypatch)
    slots = build_provider_slots()
    assert slots[0]["provider"] == "ninerouter"
    assert any(slot["provider"] == "groq" for slot in slots)


def test_ninerouter_skipped_on_missing_key(monkeypatch):
    monkeypatch.delenv("PKF_ENV", raising=False)
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("NINEROUTER_KEY", raising=False)
    monkeypatch.delenv("NINEROUTER_API_KEY", raising=False)
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    monkeypatch.setattr("pkf.ninerouter.ninerouter_health", lambda: (False, "HTTP 401: Unauthorized"))
    skip, reason = ninerouter_should_skip()
    assert skip is True
    assert "ausente" in reason.lower()
    assert default_provider() == "groq"
    slots = build_provider_slots()
    assert all(slot["provider"] != "ninerouter" for slot in slots)
    assert any(slot["provider"] == "groq" for slot in slots)


def test_ninerouter_not_skipped_when_gateway_allows_anonymous(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.delenv("NINEROUTER_KEY", raising=False)
    monkeypatch.setattr("pkf.ninerouter.ninerouter_health", lambda: (True, "ok"))
    skip, reason = ninerouter_should_skip()
    assert skip is False
    assert reason == ""


def test_ninerouter_skipped_on_http_401(monkeypatch):
    monkeypatch.delenv("PKF_ENV", raising=False)
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("NINEROUTER_KEY", "bad-key")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    monkeypatch.setattr(
        "pkf.ninerouter.ninerouter_health",
        lambda: (False, "HTTP 401: Unauthorized"),
    )
    skip, reason = ninerouter_should_skip()
    assert skip is True
    assert "401" in reason
    assert default_provider() == "groq"
    pool = ProviderPool.create(start=default_provider())
    assert pool.current_name == "groq"


def test_ninerouter_auth_warning_format():
    text = ninerouter_auth_warning("HTTP 401: Unauthorized")
    assert "[9Router]" in text
    assert "fix-ninerouter-key.sh" in text


def test_is_ninerouter_auth_error():
    assert is_ninerouter_auth_error("HTTP 401: Unauthorized")
    assert is_ninerouter_auth_error("API key required for remote API access")
    assert not is_ninerouter_auth_error("Connection refused")


def test_without_ninerouter_url_unchanged(monkeypatch):
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("PKF_PROVIDER", raising=False)
    assert default_provider() in {"groq", "ollama"}
    assert "ninerouter" not in provider_pool_names()


def test_ninerouter_provider_registered(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("NINEROUTER_MODEL", "kr/claude-sonnet-4.5")
    cfg = providers()["ninerouter"]
    assert cfg.base_url.endswith("/v1")
    assert cfg.model == "kr/claude-sonnet-4.5"


def test_ninerouter_model_default(monkeypatch):
    monkeypatch.delenv("NINEROUTER_MODEL", raising=False)
    monkeypatch.delenv("PKF_NINEROUTER_MODEL", raising=False)
    assert ninerouter_chat_model() == "auto/free"


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
