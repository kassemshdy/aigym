from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.settings import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


@lru_cache
def get_owner_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url_migrations, pool_pre_ping=True)


@lru_cache
def get_owner_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """A second, privileged connection pool for one class of query the app
    role structurally cannot make: resolving *which gym* before app.gym_id
    is known. Two legitimate call sites in app/api/auth.py, both the same
    shape — "identify the tenant, then immediately scope into
    tenant_session and stop using this connection":

    - Staff login: "which gym(s) does this password-verified person belong
      to" — staff_gym_roles is gym-scoped, so that query has no gym_id to
      scope by; it's what produces one.
    - Member self-service login-code request (decision 28): "which gym does
      this phone number belong to" — members is gym-scoped the same way,
      and a member dialing in from their own phone has no gym_id to offer
      either.

    Never used to read or write actual business data — only identity
    resolution, immediately followed by a normal RLS-scoped tenant_session.
    """
    return async_sessionmaker(get_owner_engine(), expire_on_commit=False)


@asynccontextmanager
async def tenant_session(gym_id: UUID | None) -> AsyncIterator[AsyncSession]:
    """Open one transaction scoped to a gym for Row-Level Security.

    ``set_config(..., true)`` is the parameterized equivalent of
    ``SET LOCAL app.gym_id = …``: it is scoped to this transaction only, so a
    pooled connection can never carry one gym's id into the next request, and
    unlike a raw ``SET LOCAL`` string it accepts a bound parameter safely.
    Every RLS policy reads this value; a session opened with ``gym_id=None``
    can only be used for unscoped tables (``gyms``, staff auth lookups).
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        if gym_id is not None:
            await session.execute(
                text("SELECT set_config('app.gym_id', :gym_id, true)"),
                {"gym_id": str(gym_id)},
            )
        yield session


async def db_is_reachable() -> bool:
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
