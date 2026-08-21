from pkf.config import fallback_model_on_rate_limit, ninerouter_model_chain


def test_ninerouter_model_chain_defaults(monkeypatch):
    monkeypatch.delenv("PKF_NINEROUTER_MODEL_CHAIN", raising=False)
    monkeypatch.setenv("NINEROUTER_MODEL", "oc/big-pickle")
    chain = ninerouter_model_chain()
    assert chain[0] == "oc/big-pickle"
    assert "auto/coding" in chain


def test_ninerouter_rate_limit_fallback(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("NINEROUTER_MODEL", "oc/big-pickle")
    base = "http://127.0.0.1:20128/v1"
    nxt = fallback_model_on_rate_limit("oc/big-pickle", base)
    assert nxt == "auto/coding"


def test_ninerouter_model_rejection_fallback_chain(monkeypatch):
    from pkf.config import next_ninerouter_model

    monkeypatch.setenv("NINEROUTER_MODEL", "auto/free")
    monkeypatch.setenv(
        "PKF_NINEROUTER_MODEL_CHAIN",
        "auto/free,auto,auto/coding,oc/big-pickle",
    )
    assert next_ninerouter_model("auto/free") == "auto"
