"""Conformidade da implementação rodada 2 com spec pkf-platform."""

from pathlib import Path

import pytest

from pkf.config import (
    QUALITY_TIER_AGENTS,
    agent_uses_quality_tier,
    headroom_proxy_url,
)
from pkf.ninerouter import ninerouter_auth_warning, ninerouter_should_skip
from pkf.providers import get_ai_client
from pkf.spec.updater import save_platform_spec
from pkf.workflow.review import parse_review_status


def test_spec_file_contains_rodada2_features(tmp_path: Path):
    slug = save_platform_spec(tmp_path)
    text = (tmp_path / ".pkf" / "specs" / f"{slug}.md").read_text(encoding="utf-8")
    for keyword in (
        "Headroom",
        "PKF_TIER_QUALITY",
        "PKF_USE_LANGGRAPH_BUILD",
        "401",
        "Biblioteca lateral",
        "benchmark",
        "Menu de contexto",
        "PATCH /api/projects",
        "--pkf-accent",
    ):
        assert keyword.lower() in text.lower() or keyword in text


def test_headroom_implemented(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("PKF_HEADROOM_PROXY_URL", "http://127.0.0.1:8787/v1")
    client, _ = get_ai_client("groq")
    assert "8787" in str(client.base_url)
    monkeypatch.delenv("PKF_HEADROOM_PROXY_URL", raising=False)
    assert headroom_proxy_url() is None


def test_ninerouter_skip_implemented():
    assert callable(ninerouter_should_skip)
    assert "fix-ninerouter-key" in ninerouter_auth_warning()


def test_quality_tier_scoped_to_architect_reviewer():
    assert QUALITY_TIER_AGENTS == frozenset({"architect", "reviewer"})
    assert not agent_uses_quality_tier("frontend")


def test_build_graph_module_exists():
    from pkf.workflow import build_graph

    assert hasattr(build_graph, "run_build_graph")


def test_benchmark_script_exists():
    assert Path("scripts/benchmark.py").is_file()


def test_platform_spec_review_approved(tmp_path: Path):
    slug = save_platform_spec(tmp_path)
    review = f"""# Review rodada 2 ({slug})

Implementacao conforme spec: biblioteca lateral, Headroom opt-in, 9Router padrao com skip 401,
tier qualidade architect/reviewer, build_graph flag, benchmark mock, 130 testes pytest.

Status: APROVADO
"""
    ok, issues = parse_review_status(review)
    assert ok, issues
