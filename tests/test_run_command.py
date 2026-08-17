import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from pkf.config import COMMAND_TIMEOUT
from pkf.tools.impl import run_command
from pkf.workspace import Workspace


def test_run_command_rejects_chaining(tmp_path: Path):
    ws = Workspace(tmp_path)
    for cmd in ("git status && rm -rf /", "pytest; echo x", "npm run build | tee"):
        result = run_command(ws, cmd)
        assert "bloqueado" in result.lower() or "não é suportado" in result.lower()


def test_run_command_rejects_disallowed_binary(tmp_path: Path):
    ws = Workspace(tmp_path)
    result = run_command(ws, "curl https://example.com")
    assert "não permitido" in result.lower()


def test_run_command_strips_secrets_from_env(tmp_path: Path):
    ws = Workspace(tmp_path)
    captured: dict = {}

    def fake_run(args, **kwargs):
        captured["env"] = kwargs.get("env", {})
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    with patch.dict(os.environ, {"GROQ_API_KEY": "secret", "PATH": "C:\\Windows"}, clear=False):
        with patch("pkf.tools.impl.subprocess.run", side_effect=fake_run):
            run_command(ws, "git status")
    assert "GROQ_API_KEY" not in captured.get("env", {})
    assert "PATH" in captured.get("env", {})


def test_run_command_timeout(tmp_path: Path):
    ws = Workspace(tmp_path)
    with patch("pkf.tools.impl.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="python", timeout=1)):
        result = run_command(ws, "python -c \"print(1)\"")
    assert "excedeu" in result.lower()


def test_run_command_truncates_large_output(tmp_path: Path):
    ws = Workspace(tmp_path)
    with patch("pkf.tools.impl.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout="x" * 20000,
            stderr="",
        )
        result = run_command(ws, "python -c \"print('x')\"")
    assert "truncada" in result.lower()


def test_git_status_still_allowed(tmp_path: Path):
    ws = Workspace(tmp_path)
    (tmp_path / ".git").mkdir()
    result = run_command(ws, "git status")
    assert result.startswith("exit=")
