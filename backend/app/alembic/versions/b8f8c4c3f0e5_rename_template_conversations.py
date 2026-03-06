"""rename_template_conversations

Revision ID: b8f8c4c3f0e5
Revises: a1f3c7d2b9aa
Create Date: 2026-01-19 17:08:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8f8c4c3f0e5"
down_revision: str | None = "a1f3c7d2b9aa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("template_conversation", "conversation")
    op.rename_table("template_message", "message")
    op.rename_table("template_conversation_feedback", "conversation_feedback")
    op.rename_table("template_message_feedback", "message_feedback")

    index_renames = [
        ("ix_template_conversation_is_public", "ix_conversation_is_public"),
        ("ix_template_conversation_user_id", "ix_conversation_user_id"),
        ("ix_template_message_active_child_id", "ix_message_active_child_id"),
        ("ix_template_message_conversation_id", "ix_message_conversation_id"),
        ("ix_template_message_parent_id", "ix_message_parent_id"),
        (
            "ix_template_conversation_feedback_conversation_id",
            "ix_conversation_feedback_conversation_id",
        ),
        ("ix_template_conversation_feedback_user_id", "ix_conversation_feedback_user_id"),
        ("ix_template_message_feedback_message_id", "ix_message_feedback_message_id"),
        ("ix_template_message_feedback_user_id", "ix_message_feedback_user_id"),
    ]
    for old_index, new_index in index_renames:
        op.execute(f"ALTER INDEX {old_index} RENAME TO {new_index}")

    op.execute(
        "ALTER TABLE conversation RENAME CONSTRAINT template_conversation_pkey TO conversation_pkey"
    )
    op.execute(
        "ALTER TABLE conversation RENAME CONSTRAINT "
        "template_conversation_user_id_fkey TO conversation_user_id_fkey"
    )
    op.execute("ALTER TABLE message RENAME CONSTRAINT template_message_pkey TO message_pkey")
    op.execute(
        "ALTER TABLE message RENAME CONSTRAINT "
        "template_message_parent_id_fkey TO message_parent_id_fkey"
    )
    op.execute(
        "ALTER TABLE message RENAME CONSTRAINT "
        "template_message_active_child_id_fkey TO message_active_child_id_fkey"
    )
    op.execute(
        "ALTER TABLE message RENAME CONSTRAINT "
        "template_message_conversation_id_fkey TO message_conversation_id_fkey"
    )
    op.execute(
        "ALTER TABLE conversation_feedback RENAME CONSTRAINT "
        "template_conversation_feedback_pkey TO conversation_feedback_pkey"
    )
    op.execute(
        "ALTER TABLE conversation_feedback RENAME CONSTRAINT "
        "template_conversation_feedback_conversation_id_fkey "
        "TO conversation_feedback_conversation_id_fkey"
    )
    op.execute(
        "ALTER TABLE conversation_feedback RENAME CONSTRAINT "
        "template_conversation_feedback_user_id_fkey "
        "TO conversation_feedback_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE message_feedback RENAME CONSTRAINT "
        "template_message_feedback_pkey TO message_feedback_pkey"
    )
    op.execute(
        "ALTER TABLE message_feedback RENAME CONSTRAINT "
        "template_message_feedback_message_id_fkey "
        "TO message_feedback_message_id_fkey"
    )
    op.execute(
        "ALTER TABLE message_feedback RENAME CONSTRAINT "
        "template_message_feedback_user_id_fkey "
        "TO message_feedback_user_id_fkey"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE conversation RENAME CONSTRAINT conversation_pkey TO template_conversation_pkey"
    )
    op.execute(
        "ALTER TABLE conversation RENAME CONSTRAINT "
        "conversation_user_id_fkey TO template_conversation_user_id_fkey"
    )
    op.execute("ALTER TABLE message RENAME CONSTRAINT message_pkey TO template_message_pkey")
    op.execute(
        "ALTER TABLE message RENAME CONSTRAINT "
        "message_parent_id_fkey TO template_message_parent_id_fkey"
    )
    op.execute(
        "ALTER TABLE message RENAME CONSTRAINT "
        "message_active_child_id_fkey TO template_message_active_child_id_fkey"
    )
    op.execute(
        "ALTER TABLE message RENAME CONSTRAINT "
        "message_conversation_id_fkey TO template_message_conversation_id_fkey"
    )
    op.execute(
        "ALTER TABLE conversation_feedback RENAME CONSTRAINT "
        "conversation_feedback_pkey TO template_conversation_feedback_pkey"
    )
    op.execute(
        "ALTER TABLE conversation_feedback RENAME CONSTRAINT "
        "conversation_feedback_conversation_id_fkey "
        "TO template_conversation_feedback_conversation_id_fkey"
    )
    op.execute(
        "ALTER TABLE conversation_feedback RENAME CONSTRAINT "
        "conversation_feedback_user_id_fkey "
        "TO template_conversation_feedback_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE message_feedback RENAME CONSTRAINT "
        "message_feedback_pkey TO template_message_feedback_pkey"
    )
    op.execute(
        "ALTER TABLE message_feedback RENAME CONSTRAINT "
        "message_feedback_message_id_fkey "
        "TO template_message_feedback_message_id_fkey"
    )
    op.execute(
        "ALTER TABLE message_feedback RENAME CONSTRAINT "
        "message_feedback_user_id_fkey "
        "TO template_message_feedback_user_id_fkey"
    )

    index_renames = [
        ("ix_conversation_is_public", "ix_template_conversation_is_public"),
        ("ix_conversation_user_id", "ix_template_conversation_user_id"),
        ("ix_message_active_child_id", "ix_template_message_active_child_id"),
        ("ix_message_conversation_id", "ix_template_message_conversation_id"),
        ("ix_message_parent_id", "ix_template_message_parent_id"),
        (
            "ix_conversation_feedback_conversation_id",
            "ix_template_conversation_feedback_conversation_id",
        ),
        ("ix_conversation_feedback_user_id", "ix_template_conversation_feedback_user_id"),
        ("ix_message_feedback_message_id", "ix_template_message_feedback_message_id"),
        ("ix_message_feedback_user_id", "ix_template_message_feedback_user_id"),
    ]
    for old_index, new_index in index_renames:
        op.execute(f"ALTER INDEX {old_index} RENAME TO {new_index}")

    op.rename_table("conversation", "template_conversation")
    op.rename_table("message", "template_message")
    op.rename_table("conversation_feedback", "template_conversation_feedback")
    op.rename_table("message_feedback", "template_message_feedback")
