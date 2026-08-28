"""inventory intelligence & anomalies

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-07-10 16:00:00.000000

Hand-authored to mirror the InventoryIntel/UnitRisk/Anomaly model definitions (reviewed per
ADR-011 - verified by running `alembic upgrade head` against a real Postgres instance, and
confirming a subsequent `alembic revision --autogenerate` produces an empty diff). Adds
inventory-intel:view permission grants (Admin/Manager/Analyst can view inventory intelligence
output, mirroring forecasts:view's exact role split from Phase 4 - sales gets none, same
analytics-facing pattern). Named distinctly from Phase 2's existing "inventory:view" (basic
vehicle unit/model CRUD visibility, granted to all four roles including sales) since this is a
different, more restricted capability, not a re-grant of the same key.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    (
        "inventory-intel:view",
        "View inventory intelligence: ABC/XYZ heatmap, reorder points, "
        "aging/survival risk, and anomalies",
    ),
]

ROLE_GRANTS: dict[str, list[str]] = {
    "admin": ["inventory-intel:view"],
    "manager": ["inventory-intel:view"],
    "sales": [],
    "analyst": ["inventory-intel:view"],
}


def upgrade() -> None:
    op.create_table(
        "inventory_intel",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("abc", sa.String(length=1), nullable=False),
        sa.Column("xyz", sa.String(length=1), nullable=False),
        sa.Column("revenue_share", sa.Float(), nullable=False),
        sa.Column("demand_cv", sa.Float(), nullable=False),
        sa.Column("reorder_point", sa.Float(), nullable=True),
        sa.Column("safety_stock", sa.Float(), nullable=True),
        sa.Column("service_level", sa.Float(), nullable=True),
        sa.Column("skipped_reason", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analytics_runs.id"]),
        sa.ForeignKeyConstraint(["model_id"], ["vehicle_models.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_intel_run_id_model_id_branch_id",
        "inventory_intel",
        ["run_id", "model_id", "branch_id"],
        unique=False,
    )

    op.create_table(
        "unit_risk",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("days_on_lot", sa.Integer(), nullable=False),
        sa.Column("is_aging", sa.Boolean(), nullable=False),
        sa.Column("p_sale_30d", sa.Float(), nullable=True),
        sa.Column("risk_decile", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analytics_runs.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["vehicle_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_unit_risk_run_id_unit_id", "unit_risk", ["run_id", "unit_id"], unique=False)

    op.create_table(
        "anomalies",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("entity_key", sa.String(length=255), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=True),
        sa.Column("observed", sa.Float(), nullable=False),
        sa.Column("expected", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("esd_confirmed", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analytics_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anomalies_run_id_scope", "anomalies", ["run_id", "scope"], unique=False)

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
    op.drop_index("ix_anomalies_run_id_scope", table_name="anomalies")
    op.drop_table("anomalies")
    op.drop_index("ix_unit_risk_run_id_unit_id", table_name="unit_risk")
    op.drop_table("unit_risk")
    op.drop_index("ix_inventory_intel_run_id_model_id_branch_id", table_name="inventory_intel")
    op.drop_table("inventory_intel")
