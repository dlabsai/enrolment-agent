"""add_otel_span

Revision ID: 5c2d0f4b1a90
Revises: 8d5e2a7f3c14
Create Date: 2026-01-18 03:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5c2d0f4b1a90"
down_revision: str | None = "8d5e2a7f3c14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "otel_span",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("span_id", sa.String(), nullable=False),
        sa.Column("parent_span_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("status_code", sa.String(), nullable=True),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column("start_time", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("end_time", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("events", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resource", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_otel_span_trace_id"), "otel_span", ["trace_id"], unique=False)
    op.create_index(op.f("ix_otel_span_span_id"), "otel_span", ["span_id"], unique=False)
    op.create_index(
        op.f("ix_otel_span_parent_span_id"), "otel_span", ["parent_span_id"], unique=False
    )

    op.drop_table("template_assistant_message_metadata")
    op.drop_table("chat_completion_trace")


def downgrade() -> None:
    op.create_table(
        "chat_completion_trace",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("messages", sa.String(), nullable=False),
        sa.Column("completion", sa.String(), nullable=True),
        sa.Column("completion_model", sa.String(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("guardrails", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("response_format_json_schema", sa.String(), nullable=True),
        sa.Column("tools", sa.String(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "template_assistant_message_metadata",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("guardrails", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("system_prompt_rendered", sa.String(), nullable=False),
        sa.Column("conversation_turn", sa.Integer(), nullable=False),
        sa.Column("total_time", sa.Float(), nullable=True),
        sa.Column("chatbot_chat_completion_trace_id", sa.Uuid(), nullable=True),
        sa.Column("search_model_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "guardrail_model_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("search_time", sa.Float(), nullable=True),
        sa.Column("guardrail_time", sa.Float(), nullable=True),
        sa.Column("chatbot_times", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("guardrail_times", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["chatbot_chat_completion_trace_id"], ["chat_completion_trace.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["message_id"], ["template_message.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_template_assistant_message_metadata_message_id"),
        "template_assistant_message_metadata",
        ["message_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_template_assistant_message_metadata_chatbot_chat_completion_trace_id"),
        "template_assistant_message_metadata",
        ["chatbot_chat_completion_trace_id"],
        unique=False,
    )

    op.drop_index(op.f("ix_otel_span_parent_span_id"), table_name="otel_span")
    op.drop_index(op.f("ix_otel_span_span_id"), table_name="otel_span")
    op.drop_index(op.f("ix_otel_span_trace_id"), table_name="otel_span")
    op.drop_table("otel_span")
