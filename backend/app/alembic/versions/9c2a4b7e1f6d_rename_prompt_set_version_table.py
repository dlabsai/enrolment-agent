"""rename prompt set version table

Revision ID: 9c2a4b7e1f6d
Revises: 21c6c69a8a00
Create Date: 2026-01-29 02:39:39.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "9c2a4b7e1f6d"
down_revision: str | Sequence[str] | None = "21c6c69a8a00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("chatbot_version", "prompt_set_version")
    op.execute(
        "ALTER INDEX IF EXISTS ix_chatbot_version_created_by_id "
        "RENAME TO ix_prompt_set_version_created_by_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_chatbot_version_is_deployed "
        "RENAME TO ix_prompt_set_version_is_deployed"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_chatbot_version_is_internal "
        "RENAME TO ix_prompt_set_version_is_internal"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_chatbot_version_scope RENAME TO ix_prompt_set_version_scope"
    )

    op.alter_column(
        "prompt_template", "chatbot_version_id", new_column_name="prompt_set_version_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_prompt_template_chatbot_version_id "
        "RENAME TO ix_prompt_template_prompt_set_version_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX IF EXISTS ix_prompt_template_prompt_set_version_id "
        "RENAME TO ix_prompt_template_chatbot_version_id"
    )
    op.alter_column(
        "prompt_template", "prompt_set_version_id", new_column_name="chatbot_version_id"
    )

    op.execute(
        "ALTER INDEX IF EXISTS ix_prompt_set_version_scope RENAME TO ix_chatbot_version_scope"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_prompt_set_version_is_internal "
        "RENAME TO ix_chatbot_version_is_internal"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_prompt_set_version_is_deployed "
        "RENAME TO ix_chatbot_version_is_deployed"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_prompt_set_version_created_by_id "
        "RENAME TO ix_chatbot_version_created_by_id"
    )
    op.rename_table("prompt_set_version", "chatbot_version")
