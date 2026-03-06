"""add_chatbot_version_scope_enum

Revision ID: 2f7a3c9d1b5e
Revises: 7c4b1f9a2c13
Create Date: 2026-01-22 15:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2f7a3c9d1b5e"
down_revision: str | None = "7c4b1f9a2c13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SCOPE_ENUM = sa.Enum(
    "assistant",
    "summary",
    "title",
    "title_transcript",
    "rfi_extraction",
    name="chatbot_version_scope",
)


def upgrade() -> None:
    _SCOPE_ENUM.create(op.get_bind())
    op.add_column(
        "chatbot_version",
        sa.Column("scope", _SCOPE_ENUM, nullable=False, server_default="assistant"),
    )
    op.create_index("ix_chatbot_version_scope", "chatbot_version", ["scope"])
    op.alter_column("chatbot_version", "scope", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_chatbot_version_scope", table_name="chatbot_version")
    op.drop_column("chatbot_version", "scope")
    _SCOPE_ENUM.drop(op.get_bind())
