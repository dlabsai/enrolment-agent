"""add_otel_span_is_ai

Revision ID: a1f3c7d2b9aa
Revises: 5c2d0f4b1a90
Create Date: 2026-01-19 13:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1f3c7d2b9aa"
down_revision: str | None = "5c2d0f4b1a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "otel_span",
        sa.Column("is_ai", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_otel_span_is_ai", "otel_span", ["is_ai"])
    op.execute(
        """
        UPDATE otel_span
        SET is_ai = TRUE
        WHERE attributes ? 'app.is_ai'
          AND (attributes->>'app.is_ai')::boolean IS TRUE;
        """
    )
    op.alter_column("otel_span", "is_ai", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_otel_span_is_ai", table_name="otel_span")
    op.drop_column("otel_span", "is_ai")
