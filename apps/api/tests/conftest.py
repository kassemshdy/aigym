from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import get_owner_sessionmaker
from app.main import create_app


@pytest.fixture(autouse=True)
async def clean_db() -> AsyncIterator[None]:
    """Every test starts from an empty slate. TRUNCATE ... CASCADE on the two
    tables nothing else FKs *up* to (gyms, staff_users) clears every
    gym-scoped table transitively, via the owner connection since RLS would
    otherwise block even a superuser-less TRUNCATE under FORCE ROW LEVEL
    SECURITY for non-owning roles."""
    sessionmaker = get_owner_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(text("TRUNCATE gyms, staff_users CASCADE"))
        await session.commit()
    yield


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
