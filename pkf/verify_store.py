from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pkf.config import pkf_dir

LAST_VERIFY_FILE = "last_verify.json"


def save_last_verification(
    workspace_root: Path,
    *,
    phase: str,
    ok: bool,
    result: str,
    details: dict | None = None,
) -> None:
    path = pkf_dir(workspace_root) / LAST_VERIFY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "timestamp": datetime.now(UTC).isoformat(),
        "phase": phase,
        "ok": ok,
        "result": result,
    }
    if details:
        payload["details"] = details
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def load_last_verification(workspace_root: Path) -> dict | None:
    path = pkf_dir(workspace_root) / LAST_VERIFY_FILE
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
