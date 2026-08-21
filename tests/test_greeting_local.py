"""Saudações curtas não devem chamar o gateway de IA."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pkf.greetings import greeting_reply, is_greeting
from pkf.provider_pool import ProviderPool, ProviderSlot
from pkf.router import Router
from pkf.workspace import Workspace


@pytest.mark.parametrize("text", ["oi", "Olá", "hey", "bom dia"])
def test_is_greeting(text: str) -> None:
    assert is_greeting(text)


@pytest.mark.parametrize("text", ["criar um cardápio digital", "implementar login", "obrigado"])
def test_is_greeting_skips_build_intent(text: str) -> None:
    assert not is_greeting(text)


def test_greeting_reply_mentions_pkf() -> None:
    out = greeting_reply()
    assert "PKF" in out
    assert "/spec" in out


@pytest.fixture
def router(tmp_path):
    ws = Workspace(tmp_path)
    pool = ProviderPool(
        slots=[
            ProviderSlot(
                slot_id="mock-1",
                provider="mock",
                api_key="test-key",
                tier="free",
                model="mock-model",
            )
        ],
    )
    return Router("mock", ws, ui_mode=True, client=MagicMock(), provider_pool=pool)


@pytest.mark.asyncio
async def test_handle_oi_skips_llm(router: Router) -> None:
    with patch.object(router.agents["generalista"], "process", new_callable=AsyncMock) as process:
        result = await router.handle("oi")
    process.assert_not_called()
    assert result is not None
    assert "PKF" in result
