"""alerts & notifications

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-10 18:00:00.000000

Hand-authored to mirror the AlertRule/Alert/Notification model definitions (reviewed per
ADR-011 - verified by running `alembic upgrade head` against a real Postgres instance, and
confirming a subsequent `alembic revision --autogenerate` produces an empty diff). Seeds the six
FR-061 built-in rules with DS-OPS-001's stated defaults. Adds alerts:view/alerts:manage/
alert-rules:manage permission grants.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    ("alerts:view", "View the alert notification center"),
    ("alerts:manage", "Acknowledge and resolve alerts"),
    ("alert-rules:manage", "Configure alert rule thresholds, schedules, and subscriptions"),
]

ROLE_GRANTS: dict[str, list[str]] = {
    "admin": ["alerts:view", "alerts:manage", "alert-rules:manage"],
    "manager": ["alerts:view", "alerts:manage", "alert-rules:manage"],
    "sales": ["alerts:view"],
    "analyst": ["alerts:view"],
}

# rule_key, severity, params (subscribed_roles determine notification fan-out; other keys are
# rule-specific thresholds referenced by domain/alert_rules.py)
BUILTIN_RULES: list[tuple[str, str, dict[str, object]]] = [
    (
        "stock_reorder",
        "warning",
        {"lead_time_weeks": 2, "subscribed_roles": ["admin", "manager"]},
    ),
    (
        "unit_aging",
        "warning",
        {"subscribed_roles": ["admin", "manager"]},
    ),
    (
        "sales_anomaly",
        "warning",
        {"subscribed_roles": ["admin", "manager", "analyst"]},
    ),
    (
        "forecast_stockout",
        "critical",
        {"lead_time_weeks": 2, "subscribed_roles": ["admin", "manager"]},
    ),
    (
        "discount_approval",
        "warning",
        {"subscribed_roles": ["admin", "manager"]},
    ),
    (
        "lead_idle",
        "info",
        {
            "idle_days_threshold": 14,
            "score_cutoff": None,
            "subscribed_roles": ["admin", "manager", "sales"],
        },
    ),
]


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("key", sa.String(length=30), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "INFO", "WARNING", "CRITICAL", name="alertseverity", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    op.create_table(
        "alerts",
        sa.Column("rule_key", sa.String(length=30), nullable=False),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "INFO", "WARNING", "CRITICAL", name="alertseverity", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN", "ACKNOWLEDGED", "RESOLVED", name="alertstatus", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("acknowledged_by", sa.Uuid(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_status_dedup_key", "alerts", ["status", "dedup_key"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_user_id_read_at", "notifications", ["user_id", "read_at"], unique=False
    )

    _seed_permissions()
    _seed_builtin_rules()


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


def _seed_builtin_rules() -> None:
    import uuid
    from datetime import UTC, datetime

    conn = op.get_bind()
    metadata = sa.MetaData()
    alert_rules_t = sa.Table("alert_rules", metadata, autoload_with=conn)

    now = datetime.now(UTC)
    for key, severity, params in BUILTIN_RULES:
        conn.execute(
            alert_rules_t.insert().values(
                id=uuid.uuid4(),
                key=key,
                params=params,
                severity=severity.upper(),
                enabled=True,
                version=1,
                updated_by=None,
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id_read_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_alerts_status_dedup_key", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("alert_rules")
