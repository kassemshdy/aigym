"""member coach

Revision ID: 8d2f1b6c9e30
Revises: 7c1e0a9d4b21
Create Date: 2026-09-28 18:00:00.000000

Which coach a member belongs to. Nullable and unset for every existing
member: nobody was assigned before, and guessing would put someone on the
wrong coach's list. Decision 52.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8d2f1b6c9e30'
down_revision: str | Sequence[str] | None = '7c1e0a9d4b21'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'members', sa.Column('coach_staff_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'members_coach_staff_id_fkey', 'members', 'staff_users',
        ['coach_staff_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_members_coach_staff_id', 'members', ['coach_staff_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_members_coach_staff_id', table_name='members')
    op.drop_constraint('members_coach_staff_id_fkey', 'members', type_='foreignkey')
    op.drop_column('members', 'coach_staff_id')
