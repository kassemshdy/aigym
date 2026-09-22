"""staff username and password, replacing phone and pin

Revision ID: 6f0817c26cd8
Revises: dbc5c9b72f2a
Create Date: 2026-09-15 16:58:38.893496

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6f0817c26cd8'
down_revision: str | Sequence[str] | None = 'dbc5c9b72f2a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('staff_users', sa.Column('username', sa.String(), nullable=True))
    op.add_column('staff_users', sa.Column('password_hash', sa.String(), nullable=True))
    op.add_column('staff_users', sa.Column('password_reset_at', sa.DateTime(timezone=True), nullable=True))

    # Backfill any existing row (autogenerate can't do this — hand-written,
    # per the generate-migration skill's "read it before applying" step).
    # A pre-rework account has no chosen username yet, so derive one from
    # its phone (already unique) rather than leaving it NULL, which the
    # NOT NULL constraint below would then reject.
    op.execute("UPDATE staff_users SET username = regexp_replace(phone, '[^0-9]', '', 'g') "
               "WHERE username IS NULL")

    op.alter_column('staff_users', 'username', nullable=False)
    op.create_unique_constraint('uq_staff_users_username', 'staff_users', ['username'])
    op.drop_column('staff_users', 'pin_reset_at')
    op.drop_column('staff_users', 'pin_hash')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('staff_users', sa.Column('pin_hash', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('staff_users', sa.Column('pin_reset_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.drop_constraint('uq_staff_users_username', 'staff_users', type_='unique')
    op.drop_column('staff_users', 'password_reset_at')
    op.drop_column('staff_users', 'password_hash')
    op.drop_column('staff_users', 'username')
