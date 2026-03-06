"""merge heads

Revision ID: 21c6c69a8a00
Revises: 2f7a3c9d1b5e, c7e5f1d2a9b0
Create Date: 2026-01-22 20:11:19.399009

"""

from collections.abc import Sequence

revision: str = "21c6c69a8a00"
down_revision: str | Sequence[str] | None = ("2f7a3c9d1b5e", "c7e5f1d2a9b0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
