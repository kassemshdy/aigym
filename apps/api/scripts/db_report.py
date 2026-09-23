"""Print how many rows are in every table, per gym where that applies.

The reason this exists is that there was no way to answer "what is actually
in the live database" without `railway ssh`. Before moving a database, or
after restoring one, the only honest check is counting both sides — "the
deploy went green" says nothing about whether the rows came across.

    AIGYM_OPS_COMMAND="python scripts/db_report.py"

Connects with the migrations role. As the app role this would report zero
for every gym-scoped table (decision 16: NOBYPASSRLS, and no `app.gym_id`
is set outside a request), which would look exactly like data loss.
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.settings import get_settings

COUNTS = text(
    """
    SELECT c.relname AS table_name, c.reltuples::bigint AS estimate
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
    ORDER BY c.relname
    """
)


async def main() -> None:
    engine = create_async_engine(get_settings().database_url_migrations)
    async with engine.connect() as conn:
        version = (await conn.execute(text("SELECT version()"))).scalar_one()
        print(version.split(" on ")[0])
        database = (await conn.execute(text("SELECT current_database()"))).scalar_one()
        size = (
            await conn.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))
        ).scalar_one()
        print(f"{database}, {size}\n")

        tables = [row.table_name for row in (await conn.execute(COUNTS))]
        width = max((len(t) for t in tables), default=0)
        total = 0
        for table in tables:
            # reltuples is an estimate and can be -1 on a never-analyzed
            # table, which is exactly the case right after a restore. Count
            # for real: these tables are small and the answer has to be
            # trustworthy enough to migrate on.
            count = (await conn.execute(text(f'SELECT count(*) FROM "{table}"'))).scalar_one()
            total += count
            print(f"  {table.ljust(width)}  {count}")
        print(f"\n{len(tables)} tables, {total} rows.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
