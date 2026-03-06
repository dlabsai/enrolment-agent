"""add otel span usage indexes

Revision ID: d4a1c2f9e8ab
Revises: 21c6c69a8a00
Create Date: 2026-01-23 23:58:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4a1c2f9e8ab"
down_revision: str | Sequence[str] | None = "21c6c69a8a00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_otel_span_trace_id_with_conversation
        ON otel_span (trace_id)
        WHERE attributes ? 'app.conversation_id';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_otel_span_trace_id_with_cost
        ON otel_span (trace_id)
        WHERE attributes ? 'operation.cost';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_otel_span_ai_model_time
        ON otel_span (COALESCE(start_time, created_at))
        WHERE is_ai IS TRUE AND attributes ? 'gen_ai.request.model';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_otel_span_ai_model_time")
    op.execute("DROP INDEX IF EXISTS idx_otel_span_trace_id_with_cost")
    op.execute("DROP INDEX IF EXISTS idx_otel_span_trace_id_with_conversation")
