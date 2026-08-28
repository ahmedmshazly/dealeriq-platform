"""GET /alerts (notification center: badge count + filterable list), POST /alerts/{id}/
acknowledge, POST /alerts/{id}/resolve - FR-062, FR-063.

The list is scoped to the current user's own `notifications` rows (role-based subscription
fan-out already happened when the alert was opened, per `alert_rules.py`'s `open_alert`), so a
user only ever sees alerts they're actually subscribed to.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import bad_request, not_found
from dealeriq_api.domain.models.alerts import Alert, AlertStatus, Notification
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.services.audit import write_audit_row
from dealeriq_api.schemas.alerts import AlertListResponse, AlertResponse

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
def list_alerts_route(
    status_filter: str | None = Query(default=None, alias="status"),
    severity_filter: str | None = Query(default=None, alias="severity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permission("alerts:view")),
    db: Session = Depends(get_db),
) -> AlertListResponse:
    base = (
        select(Alert)
        .join(Notification, Notification.alert_id == Alert.id)
        .where(Notification.user_id == current_user.id)
    )
    if status_filter is not None:
        base = base.where(Alert.status == status_filter)
    if severity_filter is not None:
        base = base.where(Alert.severity == severity_filter)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.execute(count_stmt).scalar_one()

    alerts = (
        db.execute(base.order_by(Alert.created_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )

    badge_count = db.execute(
        select(func.count())
        .select_from(Notification)
        .join(Alert, Alert.id == Notification.alert_id)
        .where(Notification.user_id == current_user.id, Alert.status == AlertStatus.OPEN)
    ).scalar_one()

    return AlertListResponse(
        badge_count=badge_count,
        alerts=[AlertResponse.model_validate(a, from_attributes=True) for a in alerts],
        total=total,
        limit=limit,
        offset=offset,
    )


def _resolve_alert(db: Session, alert_id: uuid.UUID) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise not_found("Alert not found.")
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert_route(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_permission("alerts:manage")),
    db: Session = Depends(get_db),
) -> AlertResponse:
    alert = _resolve_alert(db, alert_id)
    if alert.status != AlertStatus.OPEN:
        raise bad_request(
            f"Only an open alert can be acknowledged (current: {alert.status.value})."
        )

    before = alert.status.value
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now(UTC)
    write_audit_row(
        db,
        actor_id=current_user.id,
        action="alert.acknowledged",
        entity_type="alert",
        entity_id=str(alert.id),
        before={"status": before},
        after={"status": alert.status.value},
        ip=None,
    )
    db.commit()
    db.refresh(alert)
    return AlertResponse.model_validate(alert, from_attributes=True)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert_route(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_permission("alerts:manage")),
    db: Session = Depends(get_db),
) -> AlertResponse:
    alert = _resolve_alert(db, alert_id)
    if alert.status == AlertStatus.RESOLVED:
        raise bad_request("Alert is already resolved.")
    if alert.status != AlertStatus.ACKNOWLEDGED:
        raise bad_request(
            f"Only an acknowledged alert can be resolved (current: {alert.status.value})."
        )

    before = alert.status.value
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(UTC)
    write_audit_row(
        db,
        actor_id=current_user.id,
        action="alert.resolved",
        entity_type="alert",
        entity_id=str(alert.id),
        before={"status": before},
        after={"status": alert.status.value},
        ip=None,
    )
    db.commit()
    db.refresh(alert)
    return AlertResponse.model_validate(alert, from_attributes=True)
