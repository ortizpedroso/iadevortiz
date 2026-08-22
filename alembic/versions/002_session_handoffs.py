"""session handoffs + DAG task_trees metadata

Revision ID: 002
Revises: 001
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("session_handoffs", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "session_handoffs")
