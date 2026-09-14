"""Idempotency-Key enforcement — the contract .agents/skills/offline-sync
holds Phase 2 endpoints to: every write carries a client-minted
idempotency_key, and a repeat of the same key is a no-op that replays the
original result rather than re-running the write. This is what lets Phase
3's IndexedDB outbox retry a queued write after a dropped connection
without double-booking a class or double-charging a payment.

Runs as HTTP middleware, not a route dependency, because it must be able to
short-circuit a duplicate request *before* the route handler runs at all —
a dependency can reject a request but can't replay a cached response in its
place.
"""

import hashlib
import json
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.db import tenant_session
from app.models import IdempotencyKey
from app.security.jwt import InvalidTokenError, decode_access_token

MUTATING_METHODS = {"POST", "PATCH", "DELETE"}

# /auth/* issues and rotates tokens — deliberately NOT idempotent (replaying
# a login must not hand back the same tokens forever). /gyms is a one-time
# bootstrap gated by its own shared secret, not a JWT, so there's no gym_id
# to key an idempotency row on yet. Everything else under the API is a
# gym-scoped write and must carry a key.
EXEMPT_PREFIXES = ("/auth", "/gyms", "/health", "/docs", "/openapi.json", "/redoc")


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in MUTATING_METHODS or request.url.path.startswith(
            EXEMPT_PREFIXES
        ):
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return JSONResponse(
                {"detail": "Idempotency-Key header is required"}, status_code=400
            )

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            # No usable token to derive a gym_id from — let the route's own
            # auth dependency reject the request with a proper 401.
            return await call_next(request)
        try:
            claims = decode_access_token(auth_header.removeprefix("Bearer "))
        except InvalidTokenError:
            return await call_next(request)

        body = await request.body()
        request_hash = hashlib.sha256(body).hexdigest()

        async with tenant_session(claims.gym_id) as session:
            existing = (
                await session.execute(
                    select(IdempotencyKey).where(
                        IdempotencyKey.gym_id == claims.gym_id, IdempotencyKey.key == key
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.request_hash != request_hash:
                    return JSONResponse(
                        {"detail": "Idempotency-Key was already used with a different body"},
                        status_code=409,
                    )
                return JSONResponse(existing.response_body, status_code=existing.response_status)

        response = await call_next(request)

        response_body = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            response_body += chunk if isinstance(chunk, bytes) else chunk.encode()
        parsed_body = json.loads(response_body) if response_body else {}

        # Recorded regardless of status: a retried validation error should
        # replay the same rejection, not re-run (and possibly re-validate
        # differently against) the handler a second time.
        async with tenant_session(claims.gym_id) as session:
            session.add(
                IdempotencyKey(
                    gym_id=claims.gym_id,
                    key=key,
                    request_hash=request_hash,
                    response_status=response.status_code,
                    response_body=parsed_body,
                )
            )

        # Two concurrent requests racing on the same brand-new key can both
        # miss the SELECT above and both reach this INSERT; the unique
        # constraint on (gym_id, key) then fails the second one with a 500
        # instead of a clean replay. Acceptable for what this key is for —
        # a client retrying its own dropped request, not concurrent
        # submission — but a known limitation, not an oversight.
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(content=response_body, status_code=response.status_code, headers=headers)
