import asyncio
import os
from pathlib import Path

import pytest

from pkf.tools.registry import ToolRegistry
from pkf.workspace import Workspace


@pytest.mark.asyncio
async def test_concurrent_write_same_file_is_atomic(tmp_path: Path):
    ws = Workspace(tmp_path)
    registry = ToolRegistry(ws, ["write_file"])

    async def write_version(label: str) -> str:
        return await registry.execute_async(
            "write_file",
            {"path": "shared.txt", "content": f"version={label}\n" * 50},
        )

    results = await asyncio.gather(write_version("A"), write_version("B"))
    assert all("gravado" in r.lower() or "Arquivo gravado" in r for r in results)
    content = (tmp_path / "shared.txt").read_text(encoding="utf-8")
    assert content == "version=A\n" * 50 or content == "version=B\n" * 50
    assert "version=A\nversion=B" not in content.replace("\r\n", "\n")


@pytest.mark.asyncio
async def test_concurrent_write_different_files_parallel(tmp_path: Path):
    ws = Workspace(tmp_path)
    registry = ToolRegistry(ws, ["write_file"])

    async def write_file(path: str, label: str) -> str:
        return await registry.execute_async(
            "write_file",
            {"path": path, "content": f'value = "{label}"\n'},
        )

    await asyncio.gather(
        write_file("a.py", "A"),
        write_file("b.py", "B"),
    )
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == 'value = "A"\n'
    assert (tmp_path / "b.py").read_text(encoding="utf-8") == 'value = "B"\n'
