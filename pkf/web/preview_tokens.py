from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from pkf.config import auth_token

PREVIEW_TTL_SECONDS = 15 * 60


def _signing_key() -> bytes:
    explicit = os.getenv("PKF_PREVIEW_SECRET", "").strip()
    if explicit:
        return explicit.encode()
    token = auth_token()
    if token:
        return f"pkf-preview:{token}".encode()
    return b"pkf-preview-dev-only"


def issue_preview_token(path: str = "*") -> tuple[str, int]:
    """Emite token de preview de curta duração vinculado a um caminho."""
    expires = int(time.time()) + PREVIEW_TTL_SECONDS
    payload = {"exp": expires, "path": path.lstrip("/") or "*"}
    data = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_signing_key(), data.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{data}.{sig}", PREVIEW_TTL_SECONDS


def validate_preview_token(token: str | None, rel_path: str = "") -> bool:
    if not token or "." not in token:
        return False
    data, sig = token.rsplit(".", 1)
    expected = hmac.new(_signing_key(), data.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig):
        return False
    pad = "=" * (-len(data) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(data + pad))
    except (json.JSONDecodeError, ValueError):
        return False
    if int(payload.get("exp", 0)) < time.time():
        return False
    allowed = str(payload.get("path", "*"))
    if allowed == "*":
        return True
    normalized = rel_path.lstrip("/")
    return normalized == allowed or normalized.startswith(f"{allowed}/")
