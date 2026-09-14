import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.logging import configure_logging
from app.middleware.idempotency import IdempotencyMiddleware
from app.settings import get_settings

logger = logging.getLogger("aigym.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging("DEBUG" if not get_settings().is_production else "INFO")
    logger.info("startup", extra={"path": "-", "method": "-"})
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AIGym API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(IdempotencyMiddleware)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)

    return app


app = create_app()
