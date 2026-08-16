from __future__ import annotations

import pytest

from pkf.config import provider_pool_names


def test_provider_pool_dedupes_groq_openai(monkeypatch):
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "g1")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("OPENAI_API_KEY", "g2")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("GEMINI_API_KEY", "gem")
    monkeypatch.delenv("PKF_PROVIDER_POOL", raising=False)
    names = provider_pool_names()
    assert names.count("groq") + names.count("openai") == 1
    assert "gemini" in names


def test_provider_pool_respects_explicit_order(monkeypatch):
    monkeypatch.delenv("NINEROUTER_URL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("GROQ_API_KEY", "q")
    monkeypatch.setenv("PKF_PROVIDER_POOL", "gemini,groq")
    names = provider_pool_names()
    assert names[0] == "gemini"
    assert "groq" in names
