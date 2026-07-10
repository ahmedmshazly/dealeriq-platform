"""forecasting engine

Revision ID: f4a5b6c7d8e9
Revises: d2b3f4a5c6e7
Create Date: 2026-07-10 13:40:00.000000

Hand-authored to mirror the AnalyticsRun/SeriesProfile/Forecast/ForecastMetric model
definitions (reviewed per ADR-011 — verified by running `alembic upgrade head` against a real
Postgres instance, and confirming a subsequent `alembic revision --autogenerate` produces an
empty diff). Adds jobs:trigger/jobs:view/forecasts:view permission grants (FR-072: only Admins
trigger jobs; Admin/Manager/Analyst can view forecast output).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "d2b3f4a5c6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    ("jobs:trigger", "Trigger an analytics job on demand"),
    ("jobs:view", "View analytics run history"),
    ("forecasts:view", "View the forecasting leaderboard and per-series fan charts"),
]

ROLE_GRANTS: dict[str, list[str]] = {
    "admin": ["jobs:trigger", "jobs:view", "forecasts:view"],
    "manager": ["forecasts:view"],
    "sales": [],
    "analyst": ["forecasts:view"],
}


def upgrade() -> None:
    op.create_table(
        "analytics_runs",
        sa.Column("job_name", sa.String(length=60), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("code_version", sa.String(length=60), nullable=False),
        sa.Column("data_from", sa.Date(), nullable=False),
        sa.Column("data_to", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING", "SUCCEEDED", "FAILED", name="runstatus", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analytics_runs_job_name_status", "analytics_runs", ["job_name", "status"], unique=False
    )

    op.create_table(
        "series_profiles",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("series_key", sa.String(length=255), nullable=False),
        sa.Column("adi", sa.Float(), nullable=False),
        sa.Column("cv2", sa.Float(), nullable=False),
        sa.Column("pattern_class", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analytics_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_series_profiles_run_id_series_key",
        "series_profiles",
        ["run_id", "series_key"],
        unique=False,
    )

    op.create_table(
        "forecasts",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("series_key", sa.String(length=255), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("yhat", sa.Float(), nullable=False),
        sa.Column("yhat_lo80", sa.Float(), nullable=False),
        sa.Column("yhat_hi80", sa.Float(), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analytics_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_forecasts_run_id_series_key", "forecasts", ["run_id", "series_key"], unique=False
    )

    op.create_table(
        "forecast_metrics",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("series_key", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("mase", sa.Float(), nullable=False),
        sa.Column("smape", sa.Float(), nullable=False),
        sa.Column("pinball_q10", sa.Float(), nullable=False),
        sa.Column("pinball_q50", sa.Float(), nullable=False),
        sa.Column("pinball_q90", sa.Float(), nullable=False),
        sa.Column("coverage80", sa.Float(), nullable=False),
        sa.Column("is_champion", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analytics_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_forecast_metrics_run_id_series_key",
        "forecast_metrics",
        ["run_id", "series_key"],
        unique=False,
    )

    _seed_permissions()


def _seed_permissions() -> None:
    import uuid
    from datetime import UTC, datetime

    conn = op.get_bind()
    metadata = sa.MetaData()
    roles_t = sa.Table("roles", metadata, autoload_with=conn)
    permissions_t = sa.Table("permissions", metadata, autoload_with=conn)
    role_permissions_t = sa.Table("role_permissions", metadata, autoload_with=conn)

    now = datetime.now(UTC)
    role_ids = {row.key: row.id for row in conn.execute(sa.select(roles_t))}

    permission_ids: dict[str, uuid.UUID] = {}
    for key, description in PERMISSIONS:
        permission_id = uuid.uuid4()
        permission_ids[key] = permission_id
        conn.execute(
            permissions_t.insert().values(
                id=permission_id,
                key=key,
                description=description,
                created_at=now,
                updated_at=now,
            )
        )

    for role_key, granted in ROLE_GRANTS.items():
        for permission_key in granted:
            conn.execute(
                role_permissions_t.insert().values(
                    id=uuid.uuid4(),
                    role_id=role_ids[role_key],
                    permission_id=permission_ids[permission_key],
                )
            )


def downgrade() -> None:
    op.drop_table("forecast_metrics")
    op.drop_index("ix_forecasts_run_id_series_key", table_name="forecasts")
    op.drop_table("forecasts")
    op.drop_index("ix_series_profiles_run_id_series_key", table_name="series_profiles")
    op.drop_table("series_profiles")
    op.drop_index("ix_analytics_runs_job_name_status", table_name="analytics_runs")
    op.drop_table("analytics_runs")
