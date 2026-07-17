"""User management, role/permission listing, and audit-log querying (FR-004, FR-013, FR-081)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dealeriq_api.core.errors import bad_request, not_found
from dealeriq_api.domain.models.audit_log import AuditLog
from dealeriq_api.domain.models.rbac import Permission, Role, RolePermission, User
from dealeriq_api.domain.services.audit import write_audit_row


def list_users(db: Session, *, limit: int, offset: int) -> tuple[list[User], int]:
    total = db.execute(select(func.count()).select_from(User)).scalar_one()
    rows = db.execute(select(User).order_by(User.email).limit(limit).offset(offset)).scalars().all()
    return list(rows), total


def update_user(
    db: Session,
    *,
    actor_id: uuid.UUID,
    target_id: uuid.UUID,
    is_active: bool | None,
    role_key: str | None,
    unlock: bool | None,
    ip: str | None,
) -> User:
    user = db.get(User, target_id)
    if user is None:
        raise not_found("User not found.")

    before = {
        "is_active": user.is_active,
        "role_key": user.role.key,
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
    }

    if is_active is not None:
        user.is_active = is_active
    if role_key is not None:
        role = db.execute(select(Role).where(Role.key == role_key)).scalar_one_or_none()
        if role is None:
            raise bad_request(f"Unknown role '{role_key}'.")
        user.role_id = role.id
    if unlock:
        user.locked_until = None
        user.failed_login_count = 0
        user.last_failed_login_at = None

    db.flush()
    after = {
        "is_active": user.is_active,
        "role_key": user.role.key,
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
    }
    write_audit_row(
        db,
        actor_id=actor_id,
        action="user.updated",
        entity_type="user",
        entity_id=str(user.id),
        before=before,
        after=after,
        ip=ip,
    )
    db.commit()
    return user


def list_roles(db: Session) -> list[Role]:
    return list(db.execute(select(Role).order_by(Role.name)).scalars().all())


def permission_matrix(db: Session) -> list[tuple[Role, list[str]]]:
    roles = list_roles(db)
    result = []
    for role in roles:
        keys = (
            db.execute(
                select(Permission.key)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
                .order_by(Permission.key)
            )
            .scalars()
            .all()
        )
        result.append((role, list(keys)))
    return result


def list_audit_log(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str | None,
    entity_type: str | None,
    entity_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[tuple[AuditLog, str | None]], int]:
    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)

    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
        count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
        count_stmt = count_stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
        count_stmt = count_stmt.where(AuditLog.entity_id == entity_id)
    if date_from is not None:
        stmt = stmt.where(AuditLog.at >= date_from)
        count_stmt = count_stmt.where(AuditLog.at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.at <= date_to)
        count_stmt = count_stmt.where(AuditLog.at <= date_to)

    total = db.execute(count_stmt).scalar_one()
    rows = db.execute(stmt.order_by(AuditLog.at.desc()).limit(limit).offset(offset)).scalars().all()

    actor_ids = {row.actor_id for row in rows if row.actor_id is not None}
    actor_emails: dict[uuid.UUID, str] = {}
    if actor_ids:
        for user in db.execute(select(User).where(User.id.in_(actor_ids))).scalars():
            actor_emails[user.id] = user.email

    return [(row, actor_emails.get(row.actor_id) if row.actor_id else None) for row in rows], total
