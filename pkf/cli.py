from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from pkf import __version__
from pkf.config import default_provider, ui_host, ui_port
from pkf.provider_pool import ProviderPool
from pkf.router import Router
from pkf.workspace import Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pkf",
        description="PKF — IA de desenvolvimento multiagente",
    )
    parser.add_argument(
        "provider",
        nargs="?",
        default=None,
        help="Provedor: ollama, groq, gemini, kimi ou openai",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Raiz do projeto em que a IA pode ler e escrever",
    )
    parser.add_argument(
        "--fallback",
        default=None,
        help="Provedor reserva. Padrão: ollama quando o principal for kimi/openai",
    )
    parser.add_argument("--ui", action="store_true", help="Abre a interface web de chat")
    parser.add_argument("--host", default=None, help="Host da UI (padrão: PKF_HOST ou 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Porta da UI (padrão: PKF_PORT ou 8765)")
    parser.add_argument("--version", action="version", version=f"pkf {__version__}")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    provider = args.provider or default_provider()
    try:
        pool = ProviderPool.create(start=provider)
        provider = pool.current_name
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    workspace = Workspace(Path(args.workspace).resolve())
    router = Router(provider, workspace, provider_pool=pool, ui_mode=bool(args.ui))
    host = args.host or ui_host()
    port = args.port or ui_port()
    if args.ui:
        from pkf.web.server import run_ui

        try:
            run_ui(router, host=host, port=port)
        except KeyboardInterrupt:
            print("\n--- UI encerrada ---")
        return
    try:
        asyncio.run(router.start_session())
    except KeyboardInterrupt:
        print("\n--- Sessão encerrada pelo usuário ---")


if __name__ == "__main__":
    main()
