"""add_app_settings

Revision ID: 8d5e2a7f3c14
Revises: 7c4b1f9a2c13
Create Date: 2026-01-15 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8d5e2a7f3c14"
down_revision: str | None = "7c4b1f9a2c13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("university_name", sa.String(), nullable=True),
        sa.Column("university_website_url", sa.String(), nullable=True),
        sa.Column("university_admissions_phone", sa.String(), nullable=True),
        sa.Column("university_transcripts_email", sa.String(), nullable=True),
        sa.Column("university_application_url", sa.String(), nullable=True),
        sa.Column("university_accreditation_url", sa.String(), nullable=True),
        sa.Column("guardrails_blocked_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
