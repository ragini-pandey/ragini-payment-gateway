"""Enable RLS (default deny) on alembic_version bookkeeping table.

Revision ID: 0005_rls_alembic_version
Revises: 0004_rls_phase2_tables
Create Date: 2026-05-23

``alembic_version`` is Alembic's internal table tracking the current migration
revision. It contains no user data and there is no owner concept, so no
policies are defined here — RLS is enabled purely so anon / authenticated
PostgREST clients cannot read it. The backend (service role) bypasses RLS,
so ``alembic upgrade`` / ``downgrade`` continue to work normally.

This silences Supabase's "Unrestricted" warning for the table.
"""

from __future__ import annotations

from alembic import op


revision = "0005_rls_alembic_version"
down_revision = "0004_rls_phase2_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table public.alembic_version enable row level security;")


def downgrade() -> None:
    op.execute("alter table public.alembic_version disable row level security;")
