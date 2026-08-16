from __future__ import annotations

import os


def database_url() -> str | None:
    url = os.getenv("DATABASE_URL", "").strip()
    return url or None


def database_enabled() -> bool:
    return database_url() is not None


def sync_database_url() -> str | None:
    """URL síncrona para Alembic (psycopg2 / sqlite)."""
    url = database_url()
    if not url:
        return None
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url
