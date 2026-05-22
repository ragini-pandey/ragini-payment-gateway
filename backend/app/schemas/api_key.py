"""API key DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas import CamelModel

Environment = Literal["test", "live"]
ApiKeyStatus = Literal["active", "revoked", "expired"]


class CreateApiKeyRequest(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    environment: Environment = "test"
    expires_at: datetime | None = None


class RevokeApiKeyRequest(CamelModel):
    reason: str | None = Field(default=None, max_length=500)


class ApiKey(CamelModel):
    id: uuid.UUID
    name: str
    environment: Environment
    key_prefix: str
    last_four: str
    status: ApiKeyStatus
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyWithSecret(ApiKey):
    """Returned only by the create endpoint."""

    key: str
