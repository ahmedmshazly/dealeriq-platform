"""GET/POST /leads, POST /leads/{id}/transition (FR-031, FR-012)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import get_user_permissions, require_permission
from dealeriq_api.auth.ownership import require_any_permission
from dealeriq_api.auth.schemas import Page
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import forbidden
from dealeriq_api.domain.lead_service import create_lead, list_leads, transition_lead
from dealeriq_api.domain.models.lead import LeadStatus
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.schemas.leads import LeadCreateRequest, LeadResponse, LeadTransitionRequest

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.get("", response_model=Page[LeadResponse])
def list_leads_route(
    owner_id: uuid.UUID | None = None,
    status: LeadStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _current_user: User = Depends(require_permission("leads:view")),
    db: Session = Depends(get_db),
) -> Page[LeadResponse]:
    leads, total = list_leads(db, owner_id=owner_id, status=status, limit=limit, offset=offset)
    return Page(
        items=[LeadResponse.from_model(lead_row) for lead_row in leads],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=LeadResponse, status_code=201)
def create_lead_route(
    body: LeadCreateRequest,
    request: Request,
    current_user: User = Depends(require_any_permission("leads:manage_own", "leads:manage_any")),
    db: Session = Depends(get_db),
) -> LeadResponse:
    granted = get_user_permissions(db, current_user.role_id)
    if "leads:manage_any" not in granted and body.owner_id != current_user.id:
        raise forbidden("You may only create leads owned by yourself.")

    ip = request.client.host if request.client else None
    lead = create_lead(
        db,
        actor_id=current_user.id,
        customer_id=body.customer_id,
        model_id=body.model_id,
        budget_band=body.budget_band,
        owner_id=body.owner_id,
        ip=ip,
    )
    return LeadResponse.from_model(lead)


@router.post("/{lead_id}/transition", response_model=LeadResponse)
def transition_lead_route(
    lead_id: uuid.UUID,
    body: LeadTransitionRequest,
    request: Request,
    current_user: User = Depends(require_any_permission("leads:manage_own", "leads:manage_any")),
    db: Session = Depends(get_db),
) -> LeadResponse:
    ip = request.client.host if request.client else None
    lead = transition_lead(
        db,
        current_user=current_user,
        lead_id=lead_id,
        target_status=body.target_status,
        notes=body.notes,
        ip=ip,
    )
    return LeadResponse.from_model(lead)
