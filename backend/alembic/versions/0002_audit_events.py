"""audit_events — append-only audit log of dashboard mutations.

Revision ID: 0002_audit_events
Revises: 0001_phase2_schema
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op


revision = "0002_audit_events"
down_revision = "0001_phase2_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists public.audit_events (
            id              uuid primary key default gen_random_uuid(),
            actor_user_id   uuid not null,
            action          text not null,
            target_type     text not null,
            target_id       uuid not null,
            environment     text,
            metadata        jsonb not null default '{}'::jsonb,
            ip              text,
            user_agent      text,
            created_at      timestamptz not null default now()
        );
        """
    )
    op.execute(
        "create index if not exists audit_events_actor_created_idx "
        "on public.audit_events (actor_user_id, created_at desc);"
    )
    op.execute(
        "create index if not exists audit_events_target_idx "
        "on public.audit_events (target_type, target_id, created_at desc);"
    )


def downgrade() -> None:
    op.execute("drop table if exists public.audit_events;")
