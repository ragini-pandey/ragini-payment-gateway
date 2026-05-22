"""Tests for the HMAC webhook signing protocol."""

from __future__ import annotations

import time

from app.security.hmac_sign import sign, verify


def test_sign_then_verify_roundtrip(settings) -> None:
    secret = "whsec_test_secret"
    body = b'{"id":"evt_1","type":"payment.success"}'
    signed = sign(secret, body)
    assert verify(secret, signed.signature_header, body) is True


def test_tampered_body_fails(settings) -> None:
    secret = "whsec_test_secret"
    body = b'{"a":1}'
    signed = sign(secret, body)
    assert verify(secret, signed.signature_header, b'{"a":2}') is False


def test_wrong_secret_fails(settings) -> None:
    body = b"hello"
    signed = sign("secret_a", body)
    assert verify("secret_b", signed.signature_header, body) is False


def test_replay_window(settings) -> None:
    secret = "s"
    body = b"x"
    signed = sign(secret, body, timestamp=int(time.time()) - 10_000)
    assert verify(secret, signed.signature_header, body, tolerance_seconds=300) is False
