"""Enable RLS + owner SELECT policies on Phase-2 tables.

Revision ID: 0004_rls_phase2_tables
Revises: 0003_realtime_security_alerts
Create Date: 2026-05-23

Defense-in-depth: the backend connects with the service role (which bypasses
RLS), so all writes continue to work. Anonymous / authenticated PostgREST or
Supabase Realtime clients see only rows they own, and cannot write at all
(default deny — no INSERT/UPDATE/DELETE policies are defined here).

Covers tables added by ``0001_phase2_schema`` and ``0002_audit_events`` that
were not already protected by RLS in the Alembic migration history:

  * ``audit_events``         — owner column ``actor_user_id``
  * ``webhook_events``       — owner column ``user_id``
  * ``api_key_usage_events`` — owner column ``user_id`` (nullable; rows with
                               NULL owner are hidden from everyone except the
                               service role, which is the intended behavior)
  * ``security_alerts``      — owner column ``user_id``

DDL is idempotent so re-running against a DB where ``supabase/schema.sql``
already enabled these policies is a no-op.
"""

from __future__ import annotations

from alembic import op


revision = "0004_rls_phase2_tables"
down_revision = "0003_realtime_security_alerts"
branch_labels = None
depends_on = None


# (table, policy_name, owner_column)
_POLICIES: list[tuple[str, str, str]] = [
    ("audit_events", "audit events visible to actor", "actor_user_id"),
    ("webhook_events", "webhook events visible to owner", "user_id"),
    ("api_key_usage_events", "api key usage visible to owner", "user_id"),
    ("security_alerts", "security alerts visible to owner", "user_id"),
]


def upgrade() -> None:
    for table, policy, owner_col in _POLICIES:
        op.execute(f"alter table public.{table} enable row level security;")
        op.execute(f'drop policy if exists "{policy}" on public.{table};')
        op.execute(
            f'create policy "{policy}" on public.{table} '
            f"for select using (auth.uid() = {owner_col});"
        )


def downgrade() -> None:
    for table, policy, _owner_col in _POLICIES:
        op.execute(f'drop policy if exists "{policy}" on public.{table};')
        op.execute(f"alter table public.{table} disable row level security;")
