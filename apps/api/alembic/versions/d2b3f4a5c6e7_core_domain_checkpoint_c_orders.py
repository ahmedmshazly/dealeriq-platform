"""core domain checkpoint c orders

Revision ID: d2b3f4a5c6e7
Revises: c1a2f3e4d5b6
Create Date: 2026-07-10 06:30:00.000000

Hand-authored to mirror the Order/OrderEvent model definitions (reviewed per ADR-011 — verified
by running `alembic upgrade head` against a real Postgres instance). Adds orders:view/
manage_own/manage_any/approve/view_margin permission grants.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2b3f4a5c6e7"
down_revision: str | None = "c1a2f3e4d5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    ("orders:view", "View orders"),
    ("orders:manage_own", "Create/submit/deliver/cancel orders you own"),
    ("orders:manage_any", "Create/submit/deliver/cancel any order"),
    ("orders:approve", "Approve a pending_approval order"),
    ("orders:view_margin", "See negotiated price minus acquisition cost on orders"),
]

ROLE_GRANTS: dict[str, list[str]] = {
    "admin": [
        "orders:view",
        "orders:manage_any",
        "orders:approve",
        "orders:view_margin",
    ],
    "manager": [
        "orders:view",
        "orders:manage_any",
        "orders:approve",
        "orders:view_margin",
    ],
    "sales": ["orders:view", "orders:manage_own"],
    "analyst": ["orders:view"],
}


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("salesperson_id", sa.Uuid(), nullable=False),
        sa.Column("negotiated_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("discount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "payment_type",
            sa.Enum("CASH", "FINANCE", name="paymenttype", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "PENDING_APPROVAL",
                "APPROVED",
                "DELIVERED",
                "CANCELLED",
                name="orderstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["salesperson_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["vehicle_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_created_at", "orders", ["created_at"], unique=False)
    op.create_index(
        "ix_orders_salesperson_id_status", "orders", ["salesperson_id", "status"], unique=False
    )
    op.create_table(
        "order_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=False),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
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
    op.drop_table("order_events")
    op.drop_index("ix_orders_salesperson_id_status", table_name="orders")
    op.drop_index("ix_orders_created_at", table_name="orders")
    op.drop_table("orders")
