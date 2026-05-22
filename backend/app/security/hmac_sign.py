"""Outbound webhook signature: HMAC-SHA256 over ``timestamp.body``.

Header format (Stripe-compatible):

    X-Ragini-Signature: t=<unix_ts>,v1=<hex>

Receivers should:
  1. Parse t and v1 from the header.
  2. Reject if |now - t| > 5 minutes (replay protection).
  3. Compute HMAC_SHA256(secret, f"{t}.{raw_body}") and compare_digest with v1.
"""

from __future__ import annotations

import hmac
import time
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class SignedPayload:
    timestamp: int
    body: bytes
    signature_header: str  # "t=<ts>,v1=<hex>"


def sign(secret: str, body: bytes, *, timestamp: int | None = None) -> SignedPayload:
    ts = int(timestamp if timestamp is not None else time.time())
    signed = f"{ts}.".encode("utf-8") + body
    mac = hmac.new(secret.encode("utf-8"), signed, sha256).hexdigest()
    return SignedPayload(timestamp=ts, body=body, signature_header=f"t={ts},v1={mac}")


def verify(secret: str, header_value: str, body: bytes, *, tolerance_seconds: int = 300) -> bool:
    """Reference receiver-side verification — used in tests and the receipt script."""
    try:
        parts = dict(kv.split("=", 1) for kv in header_value.split(","))
        ts = int(parts["t"])
        provided = parts["v1"]
    except (ValueError, KeyError):
        return False
    if abs(int(time.time()) - ts) > tolerance_seconds:
        return False
    signed = f"{ts}.".encode("utf-8") + body
    expected = hmac.new(secret.encode("utf-8"), signed, sha256).hexdigest()
    return hmac.compare_digest(expected, provided)
