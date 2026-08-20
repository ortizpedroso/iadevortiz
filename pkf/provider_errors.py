from __future__ import annotations

from openai import APIConnectionError, APIStatusError, APITimeoutError


def is_model_not_found_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 404:
        return True
    if isinstance(exc, APIStatusError) and exc.status_code == 404:
        return True
    text = str(exc).lower()
    return (
        "model_not_found" in text
        or "does not exist" in text
        or "model `" in text
        or "invalid model" in text
    )


def is_rotatable_error(exc: Exception) -> bool:
    if isinstance(exc, APIStatusError):
        return exc.status_code in {429, 500, 502, 503, 529}
    return isinstance(exc, (APIConnectionError, APITimeoutError))


def should_rotate_provider(provider: str, exc: Exception) -> bool:
    if is_rotatable_error(exc):
        return True
    if is_model_not_found_error(exc):
        return True
    if provider != "ninerouter":
        return False
    status = getattr(exc, "status_code", None)
    return status in {401, 403}
