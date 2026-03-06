"""merge telemetry and prompt-set heads

Revision ID: d58413347996
Revises: 35b5e6f06585, 9c2a4b7e1f6d
Create Date: 2026-02-13 14:15:50.650667

"""

from collections.abc import Sequence

revision: str = "d58413347996"
down_revision: str | Sequence[str] | None = ("35b5e6f06585", "9c2a4b7e1f6d")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
