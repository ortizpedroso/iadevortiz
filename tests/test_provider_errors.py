from types import SimpleNamespace

from openai import APIStatusError

from pkf.provider_errors import (
    is_model_not_found_error,
    is_ninerouter_model_rejection,
    is_ninerouter_rotatable,
    should_rotate_provider,
)


def _status_error(status_code: int, message: str) -> APIStatusError:
    exc = APIStatusError.__new__(APIStatusError)
    exc.status_code = status_code
    Exception.__init__(exc, message)
    return exc


def test_ninerouter_401_is_rotatable():
    exc = SimpleNamespace(status_code=401)
    assert should_rotate_provider("ninerouter", exc)


def test_groq_401_not_rotatable():
    exc = SimpleNamespace(status_code=401)
    assert not should_rotate_provider("groq", exc)


def test_model_not_found_404_is_rotatable_for_any_provider():
    exc = SimpleNamespace(status_code=404)
    assert should_rotate_provider("openai", exc)
    assert should_rotate_provider("groq", exc)


def test_model_not_found_message_is_detected():
    exc = Exception(
        "Error code: 404 - {'error': {'message': \"The model 'gpt-4o-mini' does not exist\", "
        "'type': 'invalid_request_error', 'code': 'model_not_found'}}"
    )
    assert is_model_not_found_error(exc)


def test_api_status_404_is_model_not_found():
    exc = SimpleNamespace(status_code=404)
    assert is_model_not_found_error(exc)


def test_ninerouter_400_auto_free_is_model_rejection():
    exc = _status_error(400, "Invalid auto prefix format for auto/free")
    assert is_ninerouter_model_rejection(exc)
    assert is_ninerouter_rotatable(exc)


def test_ninerouter_400_unrelated_not_rotatable():
    exc = _status_error(400, "missing required field")
    assert not is_ninerouter_model_rejection(exc)
    assert not is_ninerouter_rotatable(exc)


def test_ninerouter_503_is_rotatable():
    exc = _status_error(503, "Service unavailable")
    assert is_ninerouter_rotatable(exc)
