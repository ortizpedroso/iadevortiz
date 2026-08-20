from pkf.config import headroom_proxy_url
from pkf.providers import get_ai_client


def test_headroom_proxy_url_empty_by_default(monkeypatch):
    monkeypatch.delenv("PKF_HEADROOM_PROXY_URL", raising=False)
    assert headroom_proxy_url() is None


def test_headroom_proxy_url_reads_env(monkeypatch):
    monkeypatch.setenv("PKF_HEADROOM_PROXY_URL", "http://127.0.0.1:8788/v1")
    assert headroom_proxy_url() == "http://127.0.0.1:8788/v1"


def test_get_ai_client_uses_headroom_proxy(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("PKF_HEADROOM_PROXY_URL", "http://127.0.0.1:8788/v1")
    client, config = get_ai_client("groq")
    assert str(client.base_url).rstrip("/") == "http://127.0.0.1:8788/v1"
    assert "groq.com" in config.base_url


def test_get_ai_client_without_proxy_unchanged(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("PKF_HEADROOM_PROXY_URL", raising=False)
    client, config = get_ai_client("groq")
    assert str(client.base_url).rstrip("/") == config.base_url.rstrip("/")
    assert "groq.com" in config.base_url


def test_get_ai_client_proxy_regression_same_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("PKF_HEADROOM_PROXY_URL", raising=False)
    _, config_before = get_ai_client("groq")
    monkeypatch.setenv("PKF_HEADROOM_PROXY_URL", "http://127.0.0.1:8788/v1")
    _, config_after = get_ai_client("groq")
    assert config_before.name == config_after.name
    assert config_before.model == config_after.model
    assert config_before.api_key == config_after.api_key
    assert config_before.base_url == config_after.base_url
