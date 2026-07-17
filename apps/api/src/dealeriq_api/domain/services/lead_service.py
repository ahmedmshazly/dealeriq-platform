"""Lead creation, listing, and status transitions (FR-031, FR-012)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dealeriq_api.auth.ownership import assert_owner_or_permission
from dealeriq_api.core.errors import bad_request, not_found
from dealeriq_api.domain.audit import write_audit_row
from dealeriq_api.domain.lead_state_machine import InvalidLeadTransition, validate_transition
from dealeriq_api.domain.models.lead import Lead, LeadEvent, LeadStatus
from dealeriq_api.domain.models.rbac import User


def create_lead(
    db: Session,
    *,
    actor_id: uuid.UUID,
    customer_id: uuid.UUID,
    model_id: uuid.UUID,
    budget_band: str,
    owner_id: uuid.UUID,
    ip: str | None,
) -> Lead:
    now = datetime.now(UTC)
    lead = Lead(
        customer_id=customer_id,
        model_id=model_id,
        budget_band=budget_band,
        status=LeadStatus.NEW,
        owner_id=owner_id,
        last_activity_at=now,
    )
    db.add(lead)
    db.flush()
    db.add(LeadEvent(lead_id=lead.id, type="created", actor_id=actor_id, at=now))
    write_audit_row(
        db,
        actor_id=actor_id,
        action="lead.created",
        entity_type="lead",
        entity_id=str(lead.id),
        after={
            "customer_id": str(customer_id),
            "model_id": str(model_id),
            "owner_id": str(owner_id),
        },
        ip=ip,
    )
    db.commit()
    return lead


def list_leads(
    db: Session,
    *,
    owner_id: uuid.UUID | None,
    status: LeadStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Lead], int]:
    stmt = select(Lead)
    count_stmt = select(func.count()).select_from(Lead)
    if owner_id is not None:
        stmt = stmt.where(Lead.owner_id == owner_id)
        count_stmt = count_stmt.where(Lead.owner_id == owner_id)
    if status is not None:
        stmt = stmt.where(Lead.status == status)
        count_stmt = count_stmt.where(Lead.status == status)

    total = db.execute(count_stmt).scalar_one()
    rows = (
        db.execute(stmt.order_by(Lead.last_activity_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return list(rows), total


def transition_lead(
    db: Session,
    *,
    current_user: User,
    lead_id: uuid.UUID,
    target_status: LeadStatus,
    notes: str | None,
    ip: str | None,
) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise not_found("Lead not found.")

    assert_owner_or_permission(
        db=db,
        current_user=current_user,
        any_permission_key="leads:manage_any",
        owner_id=lead.owner_id,
    )

    try:
        validate_transition(lead.status, target_status)
    except InvalidLeadTransition as exc:
        raise bad_request(str(exc)) from exc

    before_status = lead.status
    now = datetime.now(UTC)
    lead.status = target_status
    lead.last_activity_at = now
    db.add(
        LeadEvent(
            lead_id=lead.id,
            type="status_change",
            notes=notes,
            actor_id=current_user.id,
            at=now,
        )
    )
    write_audit_row(
        db,
        actor_id=current_user.id,
        action="lead.transitioned",
        entity_type="lead",
        entity_id=str(lead.id),
        before={"status": before_status.value},
        after={"status": target_status.value},
        ip=ip,
    )
    db.commit()
    return lead
