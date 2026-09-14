"""row level security for refresh tokens

Revision ID: 3bf5ae412866
Revises: 4a54ba2b0a0a
Create Date: 2026-09-14 08:47:57.680745

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3bf5ae412866'
down_revision: str | Sequence[str] | None = '4a54ba2b0a0a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# refresh_tokens joins the stage-2 GYM_SCOPED_TABLES list: same policy, same
# reasoning (see 6290203bb295_row_level_security_policies.py). member_login_codes
# is deliberately NOT here — see app/models/auth.py for why.


def upgrade() -> None:
    op.execute("ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_tokens FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON refresh_tokens
        USING (gym_id = NULLIF(current_setting('app.gym_id', true), '')::uuid)
        WITH CHECK (gym_id = NULLIF(current_setting('app.gym_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON refresh_tokens")
    op.execute("ALTER TABLE refresh_tokens NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_tokens DISABLE ROW LEVEL SECURITY")
