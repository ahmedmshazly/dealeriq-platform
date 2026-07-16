"""partial unique index: one non-RESOLVED alert per (rule_key, dedup_key) (FR-062)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-16 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # alerts.status is stored as uppercase enum labels (OPEN/ACKNOWLEDGED/RESOLVED).
    # Collapse any pre-existing duplicates before the unique index can be created.
    op.execute(
        """
        DELETE FROM alerts a
        USING alerts b
        WHERE a.rule_key = b.rule_key
          AND a.dedup_key = b.dedup_key
          AND a.status <> 'RESOLVED'
          AND b.status <> 'RESOLVED'
          AND a.created_at > b.created_at
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_alerts_open_rule_dedup
        ON alerts (rule_key, dedup_key)
        WHERE status <> 'RESOLVED'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_alerts_open_rule_dedup")
