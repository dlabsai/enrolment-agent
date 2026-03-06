"""add_catalog_document_types

Revision ID: 3b1a9e6b2b8e
Revises: 2cf06bb14675
Create Date: 2026-01-15 12:40:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "3b1a9e6b2b8e"
down_revision: str | None = "2cf06bb14675"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_type_enum ADD VALUE IF NOT EXISTS 'catalog_program'")
    op.execute("ALTER TYPE document_type_enum ADD VALUE IF NOT EXISTS 'catalog_course'")


def downgrade() -> None:
    op.execute("ALTER TYPE document_type_enum RENAME TO document_type_enum_old")
    op.execute("CREATE TYPE document_type_enum AS ENUM ('wp_page', 'wp_post', 'wp_program')")
    op.execute(
        "ALTER TABLE document ALTER COLUMN type "
        "TYPE document_type_enum USING type::text::document_type_enum"
    )
    op.execute("DROP TYPE document_type_enum_old")
