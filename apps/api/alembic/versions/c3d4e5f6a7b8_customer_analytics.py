"""customer analytics (RFM + lead scoring)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-11 12:00:00.000000

Hand-authored to mirror the CustomerRfmProfile/LeadScore model definitions (reviewed per
ADR-011 - verified by running `alembic upgrade head` against a real Postgres instance, and
confirming a subsequent `alembic revision --autogenerate` produces an empty diff). No new
permissions: the customer detail page (FR-033) and the leads list's score/explanation fields
(FR-032) both reuse the existing `customers:view`/`leads:view` permissions Phase 2 already
established.

Also seeds a seventh `alert_rules` row, `lead_score_drift` (FR-074) - reusing Phase 6's
rule_key-agnostic `alert_rules`/`alerts`/`notifications` machinery as-is (`GET /alert-rules` and
its admin UI are already generic over whatever rows exist, not hardcoded to the six FR-061
rules), so no new alert-lifecycle code or permissions are needed for this phase's drift alert.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_rfm_profiles",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("recency_score", sa.Integer(), nullable=True),
        sa.Column("frequency_score", sa.Integer(), nullable=True),
        sa.Column("monetary_score", sa.Integer(), nullable=True),
        sa.Column("segment", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analytics_runs.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_customer_rfm_profiles_run_id_customer_id",
        "customer_rfm_profiles",
        ["run_id", "customer_id"],
        unique=False,
    )

    op.create_table(
        "lead_scores",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("conversion_probability", sa.Float(), nullable=False),
        sa.Column("top_features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analytics_runs.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lead_scores_run_id_lead_id", "lead_scores", ["run_id", "lead_id"], unique=False
    )

    _seed_drift_rule()


def _seed_drift_rule() -> None:
    import uuid
    from datetime import UTC, datetime

    conn = op.get_bind()
    metadata = sa.MetaData()
    alert_rules_t = sa.Table("alert_rules", metadata, autoload_with=conn)

    now = datetime.now(UTC)
    conn.execute(
        alert_rules_t.insert().values(
            id=uuid.uuid4(),
            key="lead_score_drift",
            params={"psi_threshold": 0.25, "subscribed_roles": ["admin", "manager"]},
            severity="WARNING",
            enabled=True,
            version=1,
            updated_by=None,
            created_at=now,
            updated_at=now,
        )
    )


def downgrade() -> None:
    op.drop_index("ix_lead_scores_run_id_lead_id", table_name="lead_scores")
    op.drop_table("lead_scores")
    op.drop_index("ix_customer_rfm_profiles_run_id_customer_id", table_name="customer_rfm_profiles")
    op.drop_table("customer_rfm_profiles")
