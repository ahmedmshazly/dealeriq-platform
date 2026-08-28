"""GET /alert-rules, PATCH /alert-rules/{key} - FR-065: Managers/Admins configure rule
thresholds, schedules, and subscriptions; every change is versioned and audit-logged.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import not_found
from dealeriq_api.domain.models.alerts import AlertRule
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.services.audit import write_audit_row
from dealeriq_api.schemas.alerts import AlertRuleResponse, AlertRuleUpdateRequest

router = APIRouter(prefix="/api/v1/alert-rules", tags=["alert-rules"])


@router.get("", response_model=list[AlertRuleResponse])
def list_alert_rules_route(
    _current_user: User = Depends(require_permission("alert-rules:manage")),
    db: Session = Depends(get_db),
) -> list[AlertRuleResponse]:
    rules = db.execute(select(AlertRule).order_by(AlertRule.key)).scalars().all()
    return [AlertRuleResponse.model_validate(r, from_attributes=True) for r in rules]


@router.patch("/{key}", response_model=AlertRuleResponse)
def update_alert_rule_route(
    key: str,
    body: AlertRuleUpdateRequest,
    current_user: User = Depends(require_permission("alert-rules:manage")),
    db: Session = Depends(get_db),
) -> AlertRuleResponse:
    rule = db.execute(select(AlertRule).where(AlertRule.key == key)).scalar_one_or_none()
    if rule is None:
        raise not_found(f"Unknown alert rule '{key}'.")

    before = {"params": rule.params, "severity": rule.severity.value, "enabled": rule.enabled}
    if body.params is not None:
        rule.params = body.params
    if body.severity is not None:
        rule.severity = body.severity
    if body.enabled is not None:
        rule.enabled = body.enabled
    rule.version += 1
    rule.updated_by = current_user.id

    write_audit_row(
        db,
        actor_id=current_user.id,
        action="alert_rule.updated",
        entity_type="alert_rule",
        entity_id=rule.key,
        before=before,
        after={"params": rule.params, "severity": rule.severity.value, "enabled": rule.enabled},
        ip=None,
    )
    db.commit()
    db.refresh(rule)
    return AlertRuleResponse.model_validate(rule, from_attributes=True)
