"""program days

Revision ID: 9e4a2c7d1f58
Revises: 8d2f1b6c9e30
Create Date: 2026-09-28 18:40:00.000000

A plan's days, the day each exercise belongs to, and the plan and day each
workout session trained. Every existing plan becomes a one-day plan with
its exercises on day 0, which is exactly what it was. Decision 53.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9e4a2c7d1f58'
down_revision: str | Sequence[str] | None = '8d2f1b6c9e30'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'member_programs',
        sa.Column('days', postgresql.JSONB(), nullable=False, server_default='[]'),
    )
    op.add_column(
        'program_exercises',
        sa.Column('day_index', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'workout_sessions', sa.Column('program_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'workout_sessions_program_id_fkey', 'workout_sessions', 'member_programs',
        ['program_id'], ['id'], ondelete='SET NULL',
    )
    op.add_column('workout_sessions', sa.Column('day_index', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('workout_sessions', 'day_index')
    op.drop_constraint('workout_sessions_program_id_fkey', 'workout_sessions', type_='foreignkey')
    op.drop_column('workout_sessions', 'program_id')
    op.drop_column('program_exercises', 'day_index')
    op.drop_column('member_programs', 'days')
