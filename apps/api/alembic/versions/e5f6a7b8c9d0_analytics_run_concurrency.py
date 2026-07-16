"""partial unique index: one RUNNING analytics run per job_name (FR-072)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-16 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # analytics_runs.status is stored as uppercase enum labels (RUNNING/SUCCEEDED/FAILED)
    # from the Phase 4 Alembic create (f4a5b6c7d8e9).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_analytics_runs_job_name_running
        ON analytics_runs (job_name)
        WHERE status = 'RUNNING'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_analytics_runs_job_name_running")
