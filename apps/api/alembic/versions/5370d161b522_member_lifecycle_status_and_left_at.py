"""member lifecycle: status and left_at

Revision ID: 5370d161b522
Revises: bb1064ffb4f0
Create Date: 2026-09-24 15:10:00.000000

`status` carries a server default of 'active', which is what makes this a
one-step migration rather than the three the price snapshot needed: every
existing row is by definition an active member, so Postgres can fill the
column itself and there is nothing to guess at.

`left_at` stays nullable — null *is* the meaning for someone who has not
left. A sentinel date would have to be excluded from every "who left this
window" query forever.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5370d161b522'
down_revision: str | Sequence[str] | None = 'bb1064ffb4f0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'members',
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
    )
    op.add_column('members', sa.Column('left_at', sa.DateTime(timezone=True), nullable=True))
    # Partial index: every operational list filters to active members, and a
    # gym's leavers accumulate forever while its active roster does not.
    op.create_index(
        'ix_members_active', 'members', ['gym_id'], postgresql_where=sa.text("status = 'active'")
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_members_active', table_name='members')
    op.drop_column('members', 'left_at')
    op.drop_column('members', 'status')
