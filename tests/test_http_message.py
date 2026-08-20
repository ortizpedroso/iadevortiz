"""Tests for HTTP chat fallback (/api/message)."""

from pkf.web.server import process_user_message


def test_post_message_route_registered():
    source = open("pkf/web/server.py", encoding="utf-8").read()
    assert '"/api/message"' in source
    assert "async def post_message" in source


def test_process_user_message_empty():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    router = MagicMock()
    router.ui_mode = True
    router.snapshot.return_value = {"provider": "test"}
    history = MagicMock()
    history.append = AsyncMock()
    lock = asyncio.Lock()

    result = asyncio.run(process_user_message(router, history, "   ", lock=lock))
    assert result["type"] == "error"
    assert "vazia" in result["content"].lower()
