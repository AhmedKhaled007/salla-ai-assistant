"""Separate access-token expiry from session retention.

Revision ID: d4e5f6a7b8c9
Revises: bb447b8a06d5
Create Date: 2026-08-04 06:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "bb447b8a06d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "auth_sessions",
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
    )



def downgrade() -> None:
    op.drop_column("auth_sessions", "retention_expires_at")
