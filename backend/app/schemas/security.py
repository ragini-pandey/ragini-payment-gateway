"""Security alert DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas import CamelModel


class SecurityAlert(CamelModel):
    id: uuid.UUID
    environment: str
    api_key_id: uuid.UUID | None
    alert_type: str
    severity: str
    details: dict[str, Any]
    created_at: datetime
