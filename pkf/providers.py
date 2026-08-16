from __future__ import annotations

from dataclasses import replace

from openai import AsyncOpenAI

from pkf.config import API_TIMEOUT, ProviderConfig, providers


def get_provider(name: str) -> ProviderConfig:
    available = providers()
    if name not in available:
        raise ValueError(f"Provedor '{name}' desconhecido. Use: {list(available)}")
    config = available[name]
    if not config.api_key and name not in {"ollama", "ninerouter"}:
        raise ValueError(
            f"Chave de API para '{name}' não encontrada. Configure o arquivo .env."
        )
    return config


def get_ai_client(
    provider_name: str,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[AsyncOpenAI, ProviderConfig]:
    config = get_provider(provider_name)
    if api_key:
        config = replace(config, api_key=api_key)
    if model:
        config = replace(config, model=model)
    print(f"Conectando ao provedor '{config.name}' em: {config.base_url} ({config.model})")
    client = AsyncOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        timeout=API_TIMEOUT,
    )
    return client, config


async def ping_provider(client: AsyncOpenAI) -> tuple[bool, str]:
    try:
        import asyncio

        await asyncio.wait_for(client.models.list(), timeout=8.0)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
