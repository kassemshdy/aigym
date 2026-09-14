from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import tenant_session
from app.security.jwt import AccessTokenClaims, InvalidTokenError, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_access_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AccessTokenClaims:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


CurrentClaims = Annotated[AccessTokenClaims, Depends(get_access_claims)]


async def get_session(claims: CurrentClaims) -> AsyncIterator[AsyncSession]:
    """One transaction, scoped to the gym in the caller's access token via
    app/db.py's tenant_session. Every RLS-protected table this session
    touches is filtered to that gym — see the stage-2 policy migration."""
    async with tenant_session(claims.gym_id) as session:
        yield session


CurrentSession = Annotated[AsyncSession, Depends(get_session)]


RoleChecker = Callable[[CurrentClaims], Coroutine[None, None, AccessTokenClaims]]


def require_role(*roles: str) -> RoleChecker:
    """FastAPI dependency factory: require a staff caller whose role is one
    of `roles`. A member token never satisfies this — members and staff are
    different subject_types, not different roles."""

    async def _check(claims: CurrentClaims) -> AccessTokenClaims:
        if claims.subject_type != "staff" or claims.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return claims

    return _check
