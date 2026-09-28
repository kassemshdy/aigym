"""coaches follow staff accounts

Revision ID: 7c1e0a9d4b21
Revises: 5370d161b522
Create Date: 2026-09-28 16:30:00.000000

A member books a coach from `coaches`, but the gym's real coaches are
staff accounts (`staff_gym_roles.role = 'coach'`), and nothing connected
the two: the booking list only ever held the three placeholder coaches the
seed wrote, and a coach added under Staff never appeared in it.
`coaches.staff_user_id` was already there for exactly this link and never
set. Decision 50.

One booking profile per person per gym, enforced here rather than hoped
for in the route. Then every coach account that exists today gets one, so
a gym that added its coaches before this deploy does not have to add them
again. Their name is read from the account at request time; the copy
written here only satisfies the NOT NULL.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7c1e0a9d4b21'
down_revision: str | Sequence[str] | None = '5370d161b522'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'uq_coaches_gym_staff_user', 'coaches', ['gym_id', 'staff_user_id'], unique=True,
        postgresql_where=sa.text('staff_user_id IS NOT NULL'),
    )
    op.execute(
        """
        INSERT INTO coaches (id, gym_id, name, speciality, staff_user_id)
        SELECT gen_random_uuid(), r.gym_id,
               jsonb_build_object('ar', u.name, 'en', u.name),
               jsonb_build_object('ar', '', 'en', ''),
               u.id
        FROM staff_gym_roles r
        JOIN staff_users u ON u.id = r.staff_user_id
        WHERE r.role = 'coach'
          AND NOT EXISTS (
              SELECT 1 FROM coaches c
              WHERE c.gym_id = r.gym_id AND c.staff_user_id = u.id
          )
        """
    )


def downgrade() -> None:
    """Downgrade schema.

    Leaves the backfilled rows: they may already carry bookings, and a
    booking cascades with its coach.
    """
    op.drop_index('uq_coaches_gym_staff_user', table_name='coaches')
