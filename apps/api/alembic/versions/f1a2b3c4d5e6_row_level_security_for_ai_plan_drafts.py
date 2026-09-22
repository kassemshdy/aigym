"""row level security for ai plan drafts

Revision ID: f1a2b3c4d5e6
Revises: ef514a1883f9
Create Date: 2026-09-22 15:45:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: str | Sequence[str] | None = 'ef514a1883f9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ai_plan_drafts joins the GYM_SCOPED_TABLES list: same policy, same
# reasoning as 6290203bb295_row_level_security_policies.py.
TABLES = [
    "ai_plan_drafts",
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
