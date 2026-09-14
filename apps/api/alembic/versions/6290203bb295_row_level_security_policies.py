"""row level security policies

Revision ID: 6290203bb295
Revises: 36d3dc0d50cb
Create Date: 2026-09-14 08:39:48.843440

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6290203bb295'
down_revision: str | Sequence[str] | None = '36d3dc0d50cb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table that carries gym_id, per the stage-2 table inventory in the
# Phase 2 plan. gyms and staff_users are deliberately excluded: they are not
# gym-scoped (a gym doesn't scope itself; a staff user can hold roles at more
# than one gym). Adding a new gym-scoped table means adding it here too —
# nothing makes that automatic, which is exactly why the isolation test
# suite in stage 5 exists.
GYM_SCOPED_TABLES = [
    "staff_gym_roles",
    "members",
    "member_profiles",
    "plans",
    "subscriptions",
    "payments",
    "check_ins",
    "attendance",
    "machines",
    "coaches",
    "classes",
    "bookings",
    "idempotency_keys",
]


def upgrade() -> None:
    """Enable and FORCE Row-Level Security on every gym-scoped table, then add
    a policy that only lets a query see rows for the gym set on the current
    transaction via ``set_config('app.gym_id', …, true)`` (app/db.py).

    FORCE matters as much as ENABLE: without it, Postgres lets the table's
    *owner* bypass its own policies — and migrations run as the owner. The
    app itself connects as a separate role (aigym_app) that owns nothing and
    has NOBYPASSRLS, so FORCE is what makes the owner exemption irrelevant to
    the app's actual queries; it is not optional belt-and-braces.

    ``current_setting('app.gym_id', true)`` — the second, true, argument —
    returns NULL instead of raising when the setting was never touched this
    session, so a connection that never calls set_config sees zero rows
    rather than erroring. But Postgres resets a *touched* custom GUC to the
    empty string '', not back to NULL, once its SET LOCAL scope ends — so a
    pooled connection reused for a later, unscoped query would otherwise hit
    `''::uuid`, a hard error, instead of failing closed. NULLIF(..., '')
    turns that '' back into NULL before the cast, so both "never set" and
    "set earlier, now out of scope" fail closed the same way: zero rows, no
    exception.
    """
    for table in GYM_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (gym_id = NULLIF(current_setting('app.gym_id', true), '')::uuid)
            WITH CHECK (gym_id = NULLIF(current_setting('app.gym_id', true), '')::uuid)
            """
        )


def downgrade() -> None:
    for table in GYM_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
