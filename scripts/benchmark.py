#!/usr/bin/env python3
"""Harness interno de benchmark do pipeline /build (ferramenta manual de dev)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Specs de referência fixas (simples, para baseline repetível)
REFERENCE_SPECS: list[dict[str, str]] = [
    {
        "name": "todo-html-basico",
        "title": "Todo list HTML básico",
        "body": "# Todo HTML\n\nPágina estática com lista de tarefas, adicionar e marcar concluído.\n",
    },
    {
        "name": "api-crud-simples",
        "title": "API CRUD simples",
        "body": "# API CRUD\n\nFastAPI com endpoints GET/POST/PUT/DELETE para um recurso `items` em memória.\n",
    },
]


@dataclass
class BenchmarkRun:
    spec: str
    success: bool
    elapsed_sec: float
    retries: int = 0
    tokens: int | None = None
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


async def _run_spec_mock(workspace: Path, spec: dict[str, str]) -> BenchmarkRun:
    """Simula ciclo spec→build→review sem chamadas reais de API."""
    from pkf.spec.document import SpecDocument
    from pkf.spec.store import save_spec_document
    from pkf.workflow.review import parse_review_status

    t0 = time.perf_counter()
    try:
        doc = SpecDocument(title=spec["title"], body=spec["body"], status="approved")
        save_spec_document(workspace, spec["name"], doc)
        review_text = f"# Review — {spec['name']}\n\nStatus: APROVADO\n"
        approved, _issues = parse_review_status(review_text)
        elapsed = time.perf_counter() - t0
        return BenchmarkRun(
            spec=spec["name"],
            success=approved,
            elapsed_sec=round(elapsed, 3),
            retries=0,
            tokens=None,
        )
    except Exception as exc:
        return BenchmarkRun(
            spec=spec["name"],
            success=False,
            elapsed_sec=round(time.perf_counter() - t0, 3),
            error=str(exc),
        )


async def run_benchmark(workspace: Path, *, live: bool = False) -> list[BenchmarkRun]:
    if live:
        raise NotImplementedError(
            "Modo live (API real) não implementado — use mock (padrão) ou integre provider manualmente."
        )
    results: list[BenchmarkRun] = []
    for spec in REFERENCE_SPECS:
        results.append(await _run_spec_mock(workspace, spec))
    return results


def _print_table(runs: list[BenchmarkRun]) -> None:
    print(f"{'spec':<22} {'ok':<5} {'sec':<8} {'retries':<8} error")
    print("-" * 60)
    for run in runs:
        print(
            f"{run.spec:<22} {str(run.success):<5} {run.elapsed_sec:<8} {run.retries:<8} "
            f"{(run.error or '')[:24]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark interno PKF (/spec→/build→/review)")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(os.getenv("PKF_BENCHMARK_WORKSPACE", ".pkf/benchmark")),
        help="Diretório de workspace temporário",
    )
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    parser.add_argument("--live", action="store_true", help="Usar API real (não implementado)")
    args = parser.parse_args(argv)

    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / ".pkf" / "specs").mkdir(parents=True, exist_ok=True)

    runs = asyncio.run(run_benchmark(workspace, live=args.live))
    payload = {"runs": [asdict(r) for r in runs], "workspace": str(workspace)}

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_table(runs)
        ok = sum(1 for r in runs if r.success)
        print(f"\n{ok}/{len(runs)} specs OK — workspace: {workspace}")
    return 0 if all(r.success for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
