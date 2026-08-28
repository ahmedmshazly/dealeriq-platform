"""dashboard permissions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-11 15:00:00.000000

Hand-authored - no new tables (ADR-024: achieved accuracy is computed on demand, the sales
target is a single `Settings`-level constant, not a persisted per-salesperson quota). Seeds two
new permissions: `dashboard:view_manager` (admin/manager) and `dashboard:view_sales`
(admin/manager/sales - the sales dashboard scopes "my" data server-side by `current_user.id`
regardless of role, so managers/admins can view it too for oversight).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    ("dashboard:view_manager", "View the Manager dashboard"),
    ("dashboard:view_sales", "View the Sales dashboard"),
]

ROLE_GRANTS: dict[str, list[str]] = {
    "admin": ["dashboard:view_manager", "dashboard:view_sales"],
    "manager": ["dashboard:view_manager", "dashboard:view_sales"],
    "sales": ["dashboard:view_sales"],
    "analyst": [],
}


def upgrade() -> None:
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
    conn = op.get_bind()
    metadata = sa.MetaData()
    permissions_t = sa.Table("permissions", metadata, autoload_with=conn)
    role_permissions_t = sa.Table("role_permissions", metadata, autoload_with=conn)

    permission_ids = (
        conn.execute(
            sa.select(permissions_t.c.id).where(
                permissions_t.c.key.in_([key for key, _ in PERMISSIONS])
            )
        )
        .scalars()
        .all()
    )
    conn.execute(
        role_permissions_t.delete().where(role_permissions_t.c.permission_id.in_(permission_ids))
    )
    conn.execute(
        permissions_t.delete().where(permissions_t.c.key.in_([key for key, _ in PERMISSIONS]))
    )
