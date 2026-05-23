"""Webhook DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.events import is_valid_event_type
from app.schemas import CamelModel

Environment = Literal["test", "live"]
WebhookStatus = Literal["active", "disabled"]
DeliveryStatus = Literal["success", "failed", "pending", "retrying", "dead_lettered"]


class CreateWebhookRequest(CamelModel):
    url: HttpUrl
    description: str | None = Field(default=None, max_length=500)
    events: list[str] = Field(min_length=1)
    environment: Environment = "test"

    @field_validator("events")
    @classmethod
    def _events_known(cls, v: list[str]) -> list[str]:
        bad = [e for e in v if not is_valid_event_type(e)]
        if bad:
            raise ValueError(f"Unknown event types: {bad}")
        return v

    @model_validator(mode="after")
    def _https_required_for_live(self) -> "CreateWebhookRequest":
        if self.environment == "live" and str(self.url).startswith("http://"):
            raise ValueError("Live webhook endpoints must use HTTPS")
        return self


class UpdateWebhookRequest(CamelModel):
    url: HttpUrl | None = None
    description: str | None = None
    events: list[str] | None = None
    status: WebhookStatus | None = None

    @field_validator("events")
    @classmethod
    def _events_known(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        bad = [e for e in v if not is_valid_event_type(e)]
        if bad:
            raise ValueError(f"Unknown event types: {bad}")
        return v


class Webhook(CamelModel):
    id: uuid.UUID
    url: str
    description: str | None
    events: list[str]
    environment: Environment
    secret: str  # full secret returned at create; masked otherwise
    status: WebhookStatus
    created_at: datetime


class WebhookDelivery(CamelModel):
    id: uuid.UUID
    webhook_id: uuid.UUID
    event_type: str
    status: DeliveryStatus
    attempt: int
    response_code: int | None
    response_body: str | None
    created_at: datetime


class DeliveryListResponse(CamelModel):
    items: list[WebhookDelivery]
    total: int
    limit: int
    offset: int
