"""Request-ID correlation middleware.

Reads ``X-Request-ID`` from the incoming request if it looks like a UUID,
otherwise generates a fresh one. Binds it (plus client IP) into structlog
contextvars so every log line emitted while the request is in flight carries
``request_id``. Echoes the value back on the response so callers can correlate
their logs with ours.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER = "X-Request-ID"


def _coerce(value: str | None) -> str:
    if not value:
        return uuid.uuid4().hex
    # Accept UUID-shaped or short hex tokens; reject anything else to avoid
    # log injection (newlines, control chars, header smuggling).
    cleaned = value.strip()
    if 8 <= len(cleaned) <= 64 and all(c.isalnum() or c in "-_" for c in cleaned):
        return cleaned
    return uuid.uuid4().hex


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _coerce(request.headers.get(HEADER))
        client_ip = request.client.host if request.client else None
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            client_ip=client_ip,
            method=request.method,
            path=request.url.path,
        )
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers[HEADER] = request_id
        return response
