"""Canonical event catalog. Backend is the single source of these strings."""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    API_KEY_EXPIRED = "api_key.expired"
    API_KEY_REVOKED = "api_key.revoked"
    SECURITY_ALERT = "security.alert"
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_ERROR = "payment.error"


ALL_EVENT_TYPES: tuple[str, ...] = tuple(e.value for e in EventType)


def is_valid_event_type(value: str) -> bool:
    return value in ALL_EVENT_TYPES
