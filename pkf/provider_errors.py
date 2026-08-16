from __future__ import annotations

from openai import APIConnectionError, APIStatusError, APITimeoutError


def is_rotatable_error(exc: Exception) -> bool:
    if isinstance(exc, APIStatusError):
        return exc.status_code in {429, 500, 502, 503, 529}
    return isinstance(exc, (APIConnectionError, APITimeoutError))
