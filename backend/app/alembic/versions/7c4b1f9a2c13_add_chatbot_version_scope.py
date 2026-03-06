"""add_chatbot_version_scope

Revision ID: 7c4b1f9a2c13
Revises: 3b1a9e6b2b8e
Create Date: 2026-01-15 12:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c4b1f9a2c13"
down_revision: str | None = "3b1a9e6b2b8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chatbot_version",
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_chatbot_version_is_internal", "chatbot_version", ["is_internal"])
    op.alter_column("chatbot_version", "is_internal", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_chatbot_version_is_internal", table_name="chatbot_version")
    op.drop_column("chatbot_version", "is_internal")
