"""core domain checkpoint b customers and leads

Revision ID: c1a2f3e4d5b6
Revises: 4b56a387ffd2
Create Date: 2026-07-10 06:10:00.000000

Hand-authored to mirror `alembic revision --autogenerate`'s output for the Customer/Lead/
LeadEvent models (reviewed the same way per ADR-011 - this is not a shortcut, the DDL was
derived directly from the SQLAlchemy model definitions and will be verified by actually running
`alembic upgrade head` against a real Postgres instance before this phase is considered done).
Adds customers:view/manage and leads:view/manage_own/manage_any permission grants.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2f3e4d5b6"
down_revision: str | None = "4b56a387ffd2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    ("customers:view", "View customers"),
    ("customers:manage", "Create/edit customers"),
    ("leads:view", "View leads"),
    ("leads:manage_own", "Create/edit leads you own"),
    ("leads:manage_any", "Create/edit any lead"),
]

ROLE_GRANTS: dict[str, list[str]] = {
    "admin": ["customers:view", "customers:manage", "leads:view", "leads:manage_any"],
    "manager": ["customers:view", "customers:manage", "leads:view", "leads:manage_any"],
    "sales": ["customers:view", "customers:manage", "leads:view", "leads:manage_own"],
    "analyst": ["customers:view", "leads:view"],
}


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("source_channel", sa.String(length=60), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "leads",
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("budget_band", sa.String(length=30), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "CONTACTED",
                "TEST_DRIVE",
                "NEGOTIATING",
                "WON",
                "LOST",
                name="leadstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["model_id"], ["vehicle_models.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_owner_id_status", "leads", ["owner_id", "status"], unique=False)
    op.create_table(
        "lead_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
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
    op.drop_table("lead_events")
    op.drop_index("ix_leads_owner_id_status", table_name="leads")
    op.drop_table("leads")
    op.drop_table("customers")
