"""add otel span extracted fields

Revision ID: 35b5e6f06585
Revises: d4a1c2f9e8ab
Create Date: 2026-01-24 01:40:16.349818

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "35b5e6f06585"
down_revision: str | None = "d4a1c2f9e8ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("otel_span", sa.Column("span_time", postgresql.TIMESTAMP(timezone=True)))
    op.add_column("otel_span", sa.Column("request_model", sa.String(), nullable=True))
    op.add_column("otel_span", sa.Column("provider_name", sa.String(), nullable=True))
    op.add_column("otel_span", sa.Column("server_address", sa.String(), nullable=True))
    op.add_column("otel_span", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("otel_span", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("otel_span", sa.Column("total_cost", sa.Float(), nullable=True))
    op.add_column("otel_span", sa.Column("is_embedding", sa.Boolean(), nullable=True))
    op.add_column("otel_span", sa.Column("conversation_id", sa.Uuid(), nullable=True))
    op.add_column("otel_span", sa.Column("is_internal", sa.Boolean(), nullable=True))
    op.add_column("otel_span", sa.Column("message_id", sa.Uuid(), nullable=True))
    op.add_column("otel_span", sa.Column("total_time", sa.Float(), nullable=True))

    op.execute(
        """
        UPDATE otel_span
        SET span_time = COALESCE(start_time, created_at);
        """
    )

    op.execute(
        """
        UPDATE otel_span
        SET request_model = attributes->>'gen_ai.request.model',
            provider_name = attributes->>'gen_ai.provider.name',
            server_address = attributes->>'server.address',
            input_tokens = CASE
                WHEN (attributes->>'gen_ai.usage.input_tokens') ~ '^[0-9]+' THEN
                    (attributes->>'gen_ai.usage.input_tokens')::integer
                ELSE NULL
            END,
            output_tokens = CASE
                WHEN (attributes->>'gen_ai.usage.output_tokens') ~ '^[0-9]+' THEN
                    (attributes->>'gen_ai.usage.output_tokens')::integer
                ELSE NULL
            END,
            total_cost = CASE
                WHEN (attributes->>'operation.cost') ~ '^[0-9]+' THEN
                    (attributes->>'operation.cost')::double precision
                ELSE NULL
            END,
            is_embedding = (attributes->>'gen_ai.request.model') ILIKE '%embedding%',
            conversation_id = CASE
                WHEN (attributes->>'app.conversation_id') ~*
                    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                THEN (attributes->>'app.conversation_id')::uuid
                ELSE NULL
            END,
            is_internal = CASE
                WHEN (attributes->>'app.is_internal') IN ('true', 'false') THEN
                    (attributes->>'app.is_internal')::boolean
                ELSE NULL
            END,
            message_id = CASE
                WHEN (attributes->>'app.message_id') ~*
                    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                THEN (attributes->>'app.message_id')::uuid
                ELSE NULL
            END,
            total_time = CASE
                WHEN (attributes->>'app.total_time') ~ '^[0-9]+' THEN
                    (attributes->>'app.total_time')::double precision
                ELSE NULL
            END
        WHERE attributes IS NOT NULL;
        """
    )

    op.create_index("ix_otel_span_span_time", "otel_span", ["span_time"])
    op.create_index("ix_otel_span_request_model", "otel_span", ["request_model"])
    op.create_index("ix_otel_span_conversation_id", "otel_span", ["conversation_id"])
    op.create_index("ix_otel_span_message_id", "otel_span", ["message_id"])
    op.create_index(
        "ix_otel_span_ai_span_time",
        "otel_span",
        ["span_time"],
        postgresql_where=sa.text("is_ai IS TRUE AND request_model IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_otel_span_ai_span_time", table_name="otel_span")
    op.drop_index("ix_otel_span_message_id", table_name="otel_span")
    op.drop_index("ix_otel_span_conversation_id", table_name="otel_span")
    op.drop_index("ix_otel_span_request_model", table_name="otel_span")
    op.drop_index("ix_otel_span_span_time", table_name="otel_span")

    op.drop_column("otel_span", "total_time")
    op.drop_column("otel_span", "message_id")
    op.drop_column("otel_span", "is_internal")
    op.drop_column("otel_span", "conversation_id")
    op.drop_column("otel_span", "is_embedding")
    op.drop_column("otel_span", "total_cost")
    op.drop_column("otel_span", "output_tokens")
    op.drop_column("otel_span", "input_tokens")
    op.drop_column("otel_span", "server_address")
    op.drop_column("otel_span", "provider_name")
    op.drop_column("otel_span", "request_model")
    op.drop_column("otel_span", "span_time")
