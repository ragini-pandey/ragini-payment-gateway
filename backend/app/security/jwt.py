"""Supabase JWT verification.

Supports both HS256 (legacy shared secret) and RS256 (modern JWKS) project keys.
For HS256, set ``SUPABASE_JWT_SECRET``. For RS256, set ``SUPABASE_JWKS_URL`` and
the JWKS is fetched + cached for 1 hour.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx
from jose import JWTError, jwt

from app.config import get_settings


class JWTVerificationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: str
    email: str | None
    raw_claims: dict[str, Any]


_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_jwks_lock = Lock()
_JWKS_TTL_SECONDS = 3600


def _get_jwks() -> dict[str, Any]:
    settings = get_settings()
    if not settings.supabase_jwks_url:
        raise JWTVerificationError("SUPABASE_JWKS_URL is not configured")
    now = time.time()
    with _jwks_lock:
        if _jwks_cache["keys"] is None or now - _jwks_cache["fetched_at"] > _JWKS_TTL_SECONDS:
            resp = httpx.get(settings.supabase_jwks_url, timeout=5.0)
            resp.raise_for_status()
            _jwks_cache["keys"] = resp.json()
            _jwks_cache["fetched_at"] = now
        return _jwks_cache["keys"]  # type: ignore[return-value]


def verify_jwt(token: str) -> AuthenticatedUser:
    settings = get_settings()
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise JWTVerificationError(f"bad token header: {e}") from e

    alg = unverified_header.get("alg")
    try:
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise JWTVerificationError("SUPABASE_JWT_SECRET is not configured")
            claims = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": True},
            )
        elif alg in ("RS256", "ES256"):
            jwks = _get_jwks()
            claims = jwt.decode(
                token,
                jwks,
                algorithms=[alg],
                audience="authenticated",
                options={"verify_aud": True},
            )
        else:
            raise JWTVerificationError(f"unsupported alg: {alg}")
    except JWTError as e:
        raise JWTVerificationError(str(e)) from e

    sub = claims.get("sub")
    if not sub:
        raise JWTVerificationError("missing sub")
    return AuthenticatedUser(user_id=sub, email=claims.get("email"), raw_claims=claims)
