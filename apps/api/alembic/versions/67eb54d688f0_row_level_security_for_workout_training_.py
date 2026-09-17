"""row level security for workout training tables

Revision ID: 67eb54d688f0
Revises: fc8936ea5792
Create Date: 2026-09-17 12:00:45.342583

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '67eb54d688f0'
down_revision: str | Sequence[str] | None = 'fc8936ea5792'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The six Phase 3 floor tables join the GYM_SCOPED_TABLES list: same policy,
# same reasoning as 6290203bb295_row_level_security_policies.py.
TABLES = [
    "exercises",
    "member_programs",
    "program_exercises",
    "workout_sessions",
    "workout_sets",
    "nutrition_logs",
]


def upgrade() -> None:
    for table in TABLES:
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
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
