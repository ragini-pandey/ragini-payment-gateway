"""Enable Supabase Realtime on security_alerts table.

Revision ID: 0003_realtime_security_alerts
Revises: 0002_audit_events
Create Date: 2026-05-23
"""

from __future__ import annotations

from alembic import op


revision = "0003_realtime_security_alerts"
down_revision = "0002_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER PUBLICATION supabase_realtime ADD TABLE security_alerts;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER PUBLICATION supabase_realtime DROP TABLE security_alerts;"
    )
