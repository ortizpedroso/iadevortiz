from pkf.config import fallback_model_on_rate_limit, ninerouter_model_chain


def test_ninerouter_model_chain_defaults(monkeypatch):
    monkeypatch.delenv("PKF_NINEROUTER_MODEL_CHAIN", raising=False)
    monkeypatch.setenv("NINEROUTER_MODEL", "auto/free")
    chain = ninerouter_model_chain()
    assert chain[0] == "auto/free"
    assert "auto" in chain


def test_ninerouter_rate_limit_fallback(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("NINEROUTER_MODEL", "auto/free")
    base = "http://127.0.0.1:20128/v1"
    nxt = fallback_model_on_rate_limit("auto/free", base)
    assert nxt == "auto"
