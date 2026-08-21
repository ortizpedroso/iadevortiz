"""Compactação estruturada via LLM com fallback mecânico."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APIConnectionError

from pkf.agents.compact import (
    COMPACT_MARKER,
    _compact_messages_mechanical,
    compact_messages,
    compact_messages_llm,
)


def _long_messages(count: int = 20) -> list[dict]:
    return [
        {"role": "system", "content": "Você é agente PKF."},
        *[{"role": "user", "content": f"mensagem {i} sobre cardápio digital whitelabel"} for i in range(count)],
    ]


def _structured_summary() -> str:
    return """## Objetivo
Implementar cardápio digital whitelabel.

## Detalhes Importantes
Somente visualização, sem checkout.

## Estado do Trabalho
### Concluído
Spec aprovada.
### Ativo
Implementação frontend.
### Bloqueado
(nenhum)

## Próximo Passo
Criar index.html.

## Arquivos Relevantes
index.html: página principal
"""


@pytest.mark.asyncio
async def test_compact_messages_llm_uses_structured_template():
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=_structured_summary()))]
        )
    )
    out = await compact_messages_llm(_long_messages(), "llama-3.1-8b-instant", client)
    summary_msgs = [m for m in out if COMPACT_MARKER in (m.get("content") or "")]
    assert summary_msgs
    body = summary_msgs[-1]["content"]
    assert "## Objetivo" in body
    assert "## Arquivos Relevantes" in body
    assert "cardápio digital" in body


@pytest.mark.asyncio
async def test_compact_messages_llm_falls_back_on_llm_failure():
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=APIConnectionError(request=MagicMock()))
    out = await compact_messages_llm(_long_messages(), "llama-3.1-8b-instant", client)
    summary_msgs = [m for m in out if COMPACT_MARKER in (m.get("content") or "")]
    assert summary_msgs
    body = summary_msgs[-1]["content"]
    assert "- user:" in body


@pytest.mark.asyncio
async def test_compact_messages_llm_combines_with_previous_summary():
    client = MagicMock()
    captured: list[str] = []

    async def fake_create(**kwargs):
        captured.append(kwargs["messages"][-1]["content"])
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content=_structured_summary()))]
        )

    client.chat.completions.create = fake_create
    first = await compact_messages_llm(_long_messages(30), "llama-3.1-8b-instant", client)
    second_input = first + [{"role": "user", "content": f"extra {i} sobre deploy"} for i in range(15)]
    second = await compact_messages_llm(second_input, "llama-3.1-8b-instant", client)
    assert len(captured) >= 2
    assert "Resumo anterior" in captured[1]
    assert "cardápio digital" in captured[1]
    assert any(COMPACT_MARKER in (m.get("content") or "") for m in second)


def test_mechanical_fallback_still_used_by_sync_compact():
    out = compact_messages(_long_messages(), "llama-3.1-8b-instant")
    assert any(COMPACT_MARKER in (m.get("content") or "") for m in out)


def test_compact_messages_mechanical_alias():
    msgs = _long_messages()
    assert compact_messages(msgs) == _compact_messages_mechanical(msgs)
