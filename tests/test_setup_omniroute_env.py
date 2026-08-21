"""Garante que setup-omniroute-providers.sh não sobrescreve NINEROUTER_MODEL manual."""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path("deploy/hostinger/setup-omniroute-providers.sh")

ENV_WRITE_SNIPPET = """
grep -q '^NINEROUTER_MODEL=' .env || echo 'NINEROUTER_MODEL=auto/free' >> .env
grep -q '^PKF_NINEROUTER_MODEL_CHAIN=' .env || cat >> .env <<'EOF'
PKF_NINEROUTER_MODEL_CHAIN=auto/free,auto,auto/coding,oc/big-pickle
EOF
"""


def _run_env_snippet(env_dir: Path) -> None:
    subprocess.run(  # noqa: S603
        ["/usr/bin/bash", "-c", ENV_WRITE_SNIPPET],
        cwd=env_dir,
        check=True,
        text=True,
    )


def _read_model(env_dir: Path) -> str | None:
    for line in (env_dir / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("NINEROUTER_MODEL="):
            return line.split("=", 1)[1]
    return None


def test_script_does_not_unconditionally_overwrite_ninerouter_model() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "sed -i 's|^NINEROUTER_MODEL=.*|NINEROUTER_MODEL=auto/free|'" not in text
    assert "grep -q '^NINEROUTER_MODEL=' .env || echo 'NINEROUTER_MODEL=auto/free' >> .env" in text


def test_preserves_manual_ninerouter_model(tmp_path: Path) -> None:
    manual = "groq/openai/gpt-oss-120b"
    (tmp_path / ".env").write_text(f"NINEROUTER_MODEL={manual}\n", encoding="utf-8")
    _run_env_snippet(tmp_path)
    _run_env_snippet(tmp_path)
    assert _read_model(tmp_path) == manual


def test_sets_default_when_ninerouter_model_missing(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("PKF_PROVIDER=ninerouter\n", encoding="utf-8")
    _run_env_snippet(tmp_path)
    assert _read_model(tmp_path) == "auto/free"
