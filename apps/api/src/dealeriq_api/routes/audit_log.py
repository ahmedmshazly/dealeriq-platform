"""GET /audit-log - paginated, filterable (FR-081, API-001)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from dealeriq_api.auth.admin_service import list_audit_log
from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.auth.schemas import AuditLogEntryResponse, Page
from dealeriq_api.core.db import get_db
from dealeriq_api.domain.models.rbac import User

router = APIRouter(prefix="/api/v1/audit-log", tags=["audit-log"])


@router.get("", response_model=Page[AuditLogEntryResponse])
def list_audit_log_route(
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _current_user: User = Depends(require_permission("audit_log:view")),
    db: Session = Depends(get_db),
) -> Page[AuditLogEntryResponse]:
    rows, total = list_audit_log(
        db,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    items = [
        AuditLogEntryResponse(
            id=row.id,
            actor_id=row.actor_id,
            actor_email=actor_email,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            before=row.before_json,
            after=row.after_json,
            ip=row.ip,
            at=row.at,
        )
        for row, actor_email in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)
