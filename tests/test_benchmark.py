"""Testes do harness scripts/benchmark.py (mock, sem API)."""

from pathlib import Path

import pytest

from scripts.benchmark import REFERENCE_SPECS, run_benchmark


@pytest.mark.asyncio
async def test_benchmark_runs_without_error(tmp_path: Path):
    runs = await run_benchmark(tmp_path)
    assert len(runs) == len(REFERENCE_SPECS)
    assert all(run.success for run in runs)
    assert all(run.elapsed_sec >= 0 for run in runs)


@pytest.mark.asyncio
async def test_benchmark_creates_spec_files(tmp_path: Path):
    await run_benchmark(tmp_path)
    for spec in REFERENCE_SPECS:
        path = tmp_path / ".pkf" / "specs" / f"{spec['name']}.md"
        assert path.exists()
