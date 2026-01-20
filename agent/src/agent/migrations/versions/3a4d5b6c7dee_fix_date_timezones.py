"""fix_date_timezones

Revision ID: 3a4d5b6c7dee
Revises: c23184ad2f82
Create Date: 2026-01-20 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a4d5b6c7dee'
down_revision: Union[str, Sequence[str], None] = 'c23184ad2f82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.alter_column('users', 'created_at',
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    postgresql_using='created_at::timestamp with time zone')

    # Auth Sessions
    op.alter_column('auth_sessions', 'created_at',
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    postgresql_using='created_at::timestamp with time zone')
    op.alter_column('auth_sessions', 'updated_at',
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    postgresql_using='updated_at::timestamp with time zone')
    op.alter_column('auth_sessions', 'expires_at',
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    postgresql_using='expires_at::timestamp with time zone')

    # Conversations
    op.alter_column('conversations', 'created_at',
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    postgresql_using='created_at::timestamp with time zone')
    op.alter_column('conversations', 'updated_at',
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    postgresql_using='updated_at::timestamp with time zone')

    # Messages
    op.alter_column('messages', 'created_at',
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    postgresql_using='created_at::timestamp with time zone')


def downgrade() -> None:
    # Messages
    op.alter_column('messages', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=False)

    # Conversations
    op.alter_column('conversations', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=False)
    op.alter_column('conversations', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=False)

    # Auth Sessions
    op.alter_column('auth_sessions', 'expires_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=False)
    op.alter_column('auth_sessions', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=False)
    op.alter_column('auth_sessions', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=False)

    # Users
    op.alter_column('users', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=False)
