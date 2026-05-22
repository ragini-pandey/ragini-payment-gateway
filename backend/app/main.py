"""FastAPI app factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import configure_logging
from app.middleware.request_id import RequestIdMiddleware
from app.redis_client import close_redis
from app.routers import (
    audit,
    deliveries,
    events,
    health,
    keys,
    payments,
    security,
    webhooks,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield
    await close_redis()


_ALLOWED_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "Idempotency-Key",
    "X-Environment",
    "X-Request-ID",
]
_EXPOSE_HEADERS = ["X-Request-ID", "Retry-After"]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Ragini Payment Gateway API",
        version="0.1.0",
        lifespan=lifespan,
    )

    origins = settings.cors_origins
    allow_all = origins == ["*"]
    if allow_all:
        # Dev-only fallback; credentials cannot be combined with wildcard origin.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=_EXPOSE_HEADERS,
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=_ALLOWED_METHODS,
            allow_headers=_ALLOWED_HEADERS,
            expose_headers=_EXPOSE_HEADERS,
            max_age=600,
        )

    # Request-ID must run AFTER CORS so the header survives CORS preflight handling.
    # Starlette runs middlewares in reverse-add order, so add it LAST to run first
    # on the request path.
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health.router)
    app.include_router(keys.router)
    app.include_router(webhooks.router)
    app.include_router(deliveries.router)
    app.include_router(security.router)
    app.include_router(payments.router)
    app.include_router(events.router)
    app.include_router(audit.router)
    return app


app = create_app()
