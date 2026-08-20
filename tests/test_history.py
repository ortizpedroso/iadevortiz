from pathlib import Path

import pytest

from pkf.web.history import ChatHistory


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_chat_history_file_fallback(tmp_path: Path):
    log = ChatHistory(tmp_path)
    await log.append({"role": "user", "content": "olá"})
    again = ChatHistory(tmp_path)
    await again.load()
    assert again.messages[0]["content"] == "olá"
    await again.clear()
    fresh = ChatHistory(tmp_path)
    await fresh.load()
    assert fresh.messages == []
