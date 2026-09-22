"""row level security for member content tables

Revision ID: 42b10555715a
Revises: b199dcb1520a
Create Date: 2026-09-19 09:14:17.369923

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '42b10555715a'
down_revision: str | Sequence[str] | None = 'b199dcb1520a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The three Phase 4 content tables join the GYM_SCOPED_TABLES list: same
# policy, same reasoning as 6290203bb295_row_level_security_policies.py.
TABLES = [
    "videos",
    "food_entries",
    "progress_photos",
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
