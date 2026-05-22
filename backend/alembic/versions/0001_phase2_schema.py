"""Phase 2 schema: environments, key_id, expiry, events, usage, alerts.

Revision ID: 0001_phase2_schema
Revises:
Create Date: 2026-05-21

This migration is **additive** on top of the Phase 1 schema defined in
``supabase/schema.sql``. It assumes ``api_keys``, ``webhooks``, and
``webhook_deliveries`` already exist; if you are starting from a fresh DB,
run ``supabase/schema.sql`` first (or just ``alembic upgrade head`` — the
DDL below is idempotent via ``IF NOT EXISTS`` where possible).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_phase2_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- api_keys: add env, key_id, expiry, revocation metadata ----
    op.execute(
        """
        alter table if exists public.api_keys
            add column if not exists environment text not null default 'test',
            add column if not exists key_id      text,
            add column if not exists expires_at  timestamptz,
            add column if not exists revoked_at  timestamptz,
            add column if not exists revoked_reason text;
        """
    )
    # Backfill key_id for any pre-existing rows (random short id).
    op.execute(
        """
        update public.api_keys
           set key_id = substr(replace(gen_random_uuid()::text, '-', ''), 1, 16)
         where key_id is null;
        """
    )
    op.execute(
        """
        alter table public.api_keys
            alter column key_id set not null;
        """
    )
    op.execute(
        """
        do $$
        begin
            if not exists (
                select 1 from pg_constraint where conname = 'api_keys_key_id_unique'
            ) then
                alter table public.api_keys add constraint api_keys_key_id_unique unique (key_id);
            end if;
            if not exists (
                select 1 from pg_constraint where conname = 'api_keys_env_check'
            ) then
                alter table public.api_keys add constraint api_keys_env_check
                    check (environment in ('test','live'));
            end if;
        end$$;
        """
    )
    # Replace status check to allow 'expired'.
    op.execute(
        """
        alter table public.api_keys drop constraint if exists api_keys_status_check;
        alter table public.api_keys add constraint api_keys_status_check
            check (status in ('active','revoked','expired'));
        """
    )
    op.execute(
        "create index if not exists api_keys_user_env_status_idx "
        "on public.api_keys (user_id, environment, status);"
    )

    # ---- webhooks: add env ----
    op.execute(
        "alter table if exists public.webhooks "
        "add column if not exists environment text not null default 'test';"
    )
    op.execute(
        """
        do $$
        begin
            if not exists (select 1 from pg_constraint where conname = 'webhooks_env_check') then
                alter table public.webhooks add constraint webhooks_env_check
                    check (environment in ('test','live'));
            end if;
        end$$;
        """
    )
    op.execute(
        "create index if not exists webhooks_user_env_status_idx "
        "on public.webhooks (user_id, environment, status);"
    )

    # ---- webhook_deliveries: env, dead_lettered, next_attempt_at, event_id ----
    op.execute(
        """
        alter table if exists public.webhook_deliveries
            add column if not exists environment    text not null default 'test',
            add column if not exists next_attempt_at timestamptz,
            add column if not exists event_id       uuid;
        """
    )
    op.execute(
        """
        alter table public.webhook_deliveries drop constraint if exists webhook_deliveries_status_check;
        alter table public.webhook_deliveries add constraint webhook_deliveries_status_check
            check (status in ('success','failed','pending','retrying','dead_lettered'));
        """
    )
    op.execute(
        """
        do $$
        begin
            if not exists (
                select 1 from pg_constraint where conname = 'webhook_deliveries_env_check'
            ) then
                alter table public.webhook_deliveries add constraint webhook_deliveries_env_check
                    check (environment in ('test','live'));
            end if;
        end$$;
        """
    )

    # ---- webhook_events ----
    op.create_table(
        "webhook_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        if_not_exists=True,
    )
    op.execute(
        "create index if not exists webhook_events_user_env_idx "
        "on public.webhook_events (user_id, environment, created_at);"
    )
    # FK from webhook_deliveries.event_id → webhook_events.id (loose ON DELETE SET NULL).
    op.execute(
        """
        do $$
        begin
            if not exists (
                select 1 from pg_constraint where conname = 'webhook_deliveries_event_fk'
            ) then
                alter table public.webhook_deliveries
                    add constraint webhook_deliveries_event_fk
                    foreign key (event_id) references public.webhook_events(id) on delete set null;
            end if;
        end$$;
        """
    )

    # ---- api_key_usage_events ----
    op.create_table(
        "api_key_usage_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("environment", sa.String(), nullable=True),
        sa.Column("route", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        if_not_exists=True,
    )
    op.execute(
        "create index if not exists api_key_usage_key_created_idx "
        "on public.api_key_usage_events (api_key_id, created_at);"
    )

    # ---- security_alerts ----
    op.create_table(
        "security_alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False, server_default=sa.text("'low'")),
        sa.Column(
            "details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        if_not_exists=True,
    )
    op.execute(
        "create index if not exists security_alerts_user_created_idx "
        "on public.security_alerts (user_id, created_at);"
    )


def downgrade() -> None:
    op.execute("drop table if exists public.security_alerts;")
    op.execute("drop table if exists public.api_key_usage_events;")
    op.execute(
        "alter table if exists public.webhook_deliveries "
        "drop constraint if exists webhook_deliveries_event_fk;"
    )
    op.execute("drop table if exists public.webhook_events;")
    op.execute(
        """
        alter table if exists public.webhook_deliveries
            drop column if exists event_id,
            drop column if exists next_attempt_at,
            drop column if exists environment;
        """
    )
    op.execute("alter table if exists public.webhooks drop column if exists environment;")
    op.execute(
        """
        alter table if exists public.api_keys
            drop column if exists revoked_reason,
            drop column if exists revoked_at,
            drop column if exists expires_at,
            drop column if exists key_id,
            drop column if exists environment;
        """
    )
