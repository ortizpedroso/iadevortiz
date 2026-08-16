from types import SimpleNamespace

from pkf.provider_errors import should_rotate_provider


def test_ninerouter_401_is_rotatable():
    exc = SimpleNamespace(status_code=401)
    assert should_rotate_provider("ninerouter", exc)


def test_groq_401_not_rotatable():
    exc = SimpleNamespace(status_code=401)
    assert not should_rotate_provider("groq", exc)
