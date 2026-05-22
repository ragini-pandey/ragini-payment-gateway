"""webhooks table."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, CheckConstraint, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Webhook(Base):
    __tablename__ = "webhooks"
    __table_args__ = (
        CheckConstraint("environment in ('test','live')", name="webhooks_env_check"),
        CheckConstraint("status in ('active','disabled')", name="webhooks_status_check"),
        Index("webhooks_user_env_status_idx", "user_id", "environment", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    environment: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'test'"))
    url: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    events: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::text[]")
    )
    secret: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
