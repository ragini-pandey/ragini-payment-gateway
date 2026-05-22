"""API key generation, parsing, hashing, and constant-time verification.

Format: ``rpg_<env>_<key_id>_<secret>``

- ``env``      ∈ {"test", "live"}
- ``key_id``   16 chars, URL-safe base64-ish; globally unique, indexed for O(1) lookup
- ``secret``   32 chars, ≥190 bits of entropy

Storage:
- ``key_id``   stored plaintext (it is non-secret on its own)
- ``key_hash`` = ``HMAC_SHA256(API_KEY_PEPPER, secret)`` (hex)

Verification (sub-ms):
1. Parse incoming string → env, key_id, secret.
2. SELECT row WHERE key_id = ? (unique index).
3. Check env matches column; check status='active'; check expires_at is null or future.
4. ``hmac.compare_digest(stored_hash, hmac_sha256(secret, pepper))``.

The pepper lives only in the backend env (`API_KEY_PEPPER`). A DB leak alone
is therefore insufficient to brute-force keys — an attacker also needs the
pepper. ``hmac.compare_digest`` is constant-time.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from app.config import get_settings

Environment = Literal["test", "live"]

# URL-safe base62 alphabet (no padding chars, no separators that conflict with '_').
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
_KEY_ID_LEN = 16
_SECRET_LEN = 32
_PREFIX = "rpg"


class InvalidApiKey(ValueError):
    """Raised when an API key string cannot be parsed."""


@dataclass(frozen=True, slots=True)
class GeneratedKey:
    plaintext: str
    environment: Environment
    key_id: str
    key_hash: str
    last_four: str
    key_prefix: str  # e.g. "rpg_live_"


@dataclass(frozen=True, slots=True)
class ParsedKey:
    environment: Environment
    key_id: str
    secret: str


def _random_string(length: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def generate(environment: Environment) -> GeneratedKey:
    if environment not in ("test", "live"):
        raise ValueError(f"Invalid environment: {environment!r}")
    key_id = _random_string(_KEY_ID_LEN)
    secret = _random_string(_SECRET_LEN)
    plaintext = f"{_PREFIX}_{environment}_{key_id}_{secret}"
    return GeneratedKey(
        plaintext=plaintext,
        environment=environment,
        key_id=key_id,
        key_hash=hash_secret(secret),
        last_four=secret[-4:],
        key_prefix=f"{_PREFIX}_{environment}_",
    )


def parse(plaintext: str) -> ParsedKey:
    if not plaintext or not isinstance(plaintext, str):
        raise InvalidApiKey("empty key")
    parts = plaintext.split("_")
    if len(parts) != 4:
        raise InvalidApiKey("malformed key")
    prefix, env, key_id, secret = parts
    if prefix != _PREFIX:
        raise InvalidApiKey("bad prefix")
    if env not in ("test", "live"):
        raise InvalidApiKey("bad environment")
    if len(key_id) != _KEY_ID_LEN or len(secret) != _SECRET_LEN:
        raise InvalidApiKey("bad length")
    return ParsedKey(environment=env, key_id=key_id, secret=secret)  # type: ignore[arg-type]


def hash_secret(secret: str) -> str:
    """HMAC-SHA256 of the secret using the server-side pepper. Returns hex."""
    pepper = get_settings().api_key_pepper_bytes
    return hmac.new(pepper, secret.encode("utf-8"), sha256).hexdigest()


def verify(secret: str, stored_hash: str) -> bool:
    """Constant-time comparison."""
    candidate = hash_secret(secret)
    return hmac.compare_digest(candidate, stored_hash)


def mask(plaintext: str) -> str:
    """For display only — should never be needed server-side, but handy in logs."""
    try:
        p = parse(plaintext)
    except InvalidApiKey:
        return "rpg_***"
    return f"{_PREFIX}_{p.environment}_{p.key_id}_…{p.secret[-4:]}"
