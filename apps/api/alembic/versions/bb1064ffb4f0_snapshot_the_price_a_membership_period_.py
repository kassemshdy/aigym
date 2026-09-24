"""snapshot the price and length a membership period was sold at

Revision ID: bb1064ffb4f0
Revises: d2c2cd8e06c7
Create Date: 2026-09-24 13:34:32.503829

Three steps rather than autogenerate's one. A bare NOT NULL ADD COLUMN
fails on any database that already holds subscriptions, and while the live
database had none when this was written, local and CI databases do.

**The backfill is a guess, and the only honest one available.** It copies
each plan's price and length *as they are today* onto every period already
sold under it, which is precisely the assumption these columns exist to
stop making — nothing anywhere recorded the real figures. Rows created from
here on carry the truth. Rows older than this migration are as accurate as
the plan was stable, which for a gym that never edited one is exact and for
one that did is wrong in the old way, once, forever.

Applying this before a gym has taken real payments avoids that entirely,
which is why it went in while `subscriptions` was still empty.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'bb1064ffb4f0'
down_revision: str | Sequence[str] | None = 'd2c2cd8e06c7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'subscriptions',
        sa.Column('price_usd', sa.Numeric(precision=8, scale=2, asdecimal=False), nullable=True),
    )
    op.add_column('subscriptions', sa.Column('days', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE subscriptions s
        SET price_usd = p.price_usd, days = p.days
        FROM plans p
        WHERE p.id = s.plan_id AND (s.price_usd IS NULL OR s.days IS NULL)
        """
    )
    # A row whose plan has since vanished cannot be recovered at all. The FK
    # is ondelete=RESTRICT so this should be unreachable; it keeps the NOT
    # NULL below from failing on a database that found a way anyway, and a
    # zero price is visibly wrong rather than quietly plausible. `days`
    # falls back to 1 instead of 0 because compute_dues divides by it.
    op.execute("UPDATE subscriptions SET price_usd = 0 WHERE price_usd IS NULL")
    op.execute("UPDATE subscriptions SET days = 1 WHERE days IS NULL")
    op.alter_column('subscriptions', 'price_usd', nullable=False)
    op.alter_column('subscriptions', 'days', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('subscriptions', 'days')
    op.drop_column('subscriptions', 'price_usd')
