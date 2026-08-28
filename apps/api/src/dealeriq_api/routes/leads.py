"""GET/POST /leads, POST /leads/{id}/transition (FR-031, FR-012)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import get_user_permissions, require_permission
from dealeriq_api.auth.ownership import require_any_permission, resolve_owner_filter
from dealeriq_api.auth.schemas import Page
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import forbidden
from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus
from dealeriq_api.domain.models.customer_analytics import CustomerRfmProfile, LeadScore
from dealeriq_api.domain.models.lead import Lead, LeadStatus
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.services.lead_service import create_lead, list_leads, transition_lead
from dealeriq_api.schemas.leads import (
    FeatureContributionResponse,
    LeadCreateRequest,
    LeadResponse,
    LeadTransitionRequest,
)

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


def _latest_succeeded_lead_scoring_run_id(db: Session) -> uuid.UUID | None:
    row = db.execute(
        select(AnalyticsRun.id)
        .where(AnalyticsRun.job_name == "lead_scoring", AnalyticsRun.status == RunStatus.SUCCEEDED)
        .order_by(AnalyticsRun.finished_at.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def _enrich_leads_with_scores(db: Session, leads: list[Lead]) -> list[LeadResponse]:
    """Batch-loads the latest lead-scoring run's `LeadScore`/`CustomerRfmProfile` rows for this
    page of leads, rather than a per-lead query - one round-trip regardless of page size."""
    run_id = _latest_succeeded_lead_scoring_run_id(db)
    if run_id is None or not leads:
        return [LeadResponse.from_model(lead) for lead in leads]

    lead_ids = [lead.id for lead in leads]
    customer_ids = [lead.customer_id for lead in leads]

    scores_by_lead_id = {
        row.lead_id: row
        for row in db.execute(
            select(LeadScore).where(LeadScore.run_id == run_id, LeadScore.lead_id.in_(lead_ids))
        ).scalars()
    }
    rfm_by_customer_id = {
        row.customer_id: row
        for row in db.execute(
            select(CustomerRfmProfile).where(
                CustomerRfmProfile.run_id == run_id,
                CustomerRfmProfile.customer_id.in_(customer_ids),
            )
        ).scalars()
    }

    responses = []
    for lead in leads:
        score = scores_by_lead_id.get(lead.id)
        rfm = rfm_by_customer_id.get(lead.customer_id)
        responses.append(
            LeadResponse.from_model(
                lead,
                conversion_probability=score.conversion_probability if score else None,
                rfm_segment=rfm.segment if rfm else None,
                top_features=(
                    [
                        FeatureContributionResponse(
                            label=str(f["label"]),
                            contribution=float(f["contribution"]),  # type: ignore[arg-type]
                        )
                        for f in score.top_features
                    ]
                    if score
                    else None
                ),
            )
        )
    return responses


@router.get("", response_model=Page[LeadResponse])
def list_leads_route(
    owner_id: uuid.UUID | None = None,
    status: LeadStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permission("leads:view")),
    db: Session = Depends(get_db),
) -> Page[LeadResponse]:
    granted = get_user_permissions(db, current_user.role_id)
    scoped_owner_id = resolve_owner_filter(
        granted=granted,
        manage_any_key="leads:manage_any",
        manage_own_key="leads:manage_own",
        current_user_id=current_user.id,
        requested_owner_id=owner_id,
    )
    leads, total = list_leads(
        db, owner_id=scoped_owner_id, status=status, limit=limit, offset=offset
    )
    return Page(
        items=_enrich_leads_with_scores(db, leads),
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
