"""GET/POST /customers, GET /customers/{id} (FR-030, FR-033)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import get_user_permissions, require_permission
from dealeriq_api.auth.ownership import resolve_owner_filter
from dealeriq_api.auth.schemas import Page
from dealeriq_api.core.db import get_db
from dealeriq_api.core.errors import not_found
from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.customer_analytics import CustomerRfmProfile
from dealeriq_api.domain.models.order import Order
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import VehicleModel, VehicleUnit
from dealeriq_api.domain.services.customer_service import create_customer, list_customers
from dealeriq_api.schemas.customers import (
    CustomerCreateRequest,
    CustomerCreateResponse,
    CustomerDetailResponse,
    CustomerOrderSummaryResponse,
    CustomerResponse,
)

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def _latest_succeeded_lead_scoring_run_id(db: Session) -> uuid.UUID | None:
    row = db.execute(
        select(AnalyticsRun.id)
        .where(AnalyticsRun.job_name == "lead_scoring", AnalyticsRun.status == RunStatus.SUCCEEDED)
        .order_by(AnalyticsRun.finished_at.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


@router.get("", response_model=Page[CustomerResponse])
def list_customers_route(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _current_user: User = Depends(require_permission("customers:view")),
    db: Session = Depends(get_db),
) -> Page[CustomerResponse]:
    customers, total = list_customers(db, limit=limit, offset=offset)
    return Page(
        items=[CustomerResponse.from_model(c) for c in customers],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=CustomerCreateResponse, status_code=201)
def create_customer_route(
    body: CustomerCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("customers:manage")),
    db: Session = Depends(get_db),
) -> CustomerCreateResponse:
    ip = request.client.host if request.client else None
    customer, duplicates = create_customer(
        db,
        actor_id=current_user.id,
        name=body.name,
        phone=body.phone,
        email=body.email,
        city=body.city,
        source_channel=body.source_channel,
        ip=ip,
    )
    return CustomerCreateResponse(
        customer=CustomerResponse.from_model(customer),
        possible_duplicate_ids=[d.id for d in duplicates],
    )


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
def get_customer_route(
    customer_id: uuid.UUID,
    current_user: User = Depends(require_permission("customers:view")),
    db: Session = Depends(get_db),
) -> CustomerDetailResponse:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer not found.")

    rfm_segment = recency_score = frequency_score = monetary_score = None
    run_id = _latest_succeeded_lead_scoring_run_id(db)
    if run_id is not None:
        profile = db.execute(
            select(CustomerRfmProfile).where(
                CustomerRfmProfile.run_id == run_id, CustomerRfmProfile.customer_id == customer_id
            )
        ).scalar_one_or_none()
        if profile is not None:
            rfm_segment = profile.segment
            recency_score = profile.recency_score
            frequency_score = profile.frequency_score
            monetary_score = profile.monetary_score

    granted = get_user_permissions(db, current_user.role_id)
    scoped_salesperson_id = resolve_owner_filter(
        granted=granted,
        manage_any_key="orders:manage_any",
        manage_own_key="orders:manage_own",
        current_user_id=current_user.id,
        requested_owner_id=None,
    )
    order_query = (
        select(
            Order.id,
            Order.created_at,
            Order.negotiated_price,
            Order.status,
            VehicleModel.make,
            VehicleModel.model,
        )
        .select_from(Order)
        .join(VehicleUnit, VehicleUnit.id == Order.unit_id)
        .join(VehicleModel, VehicleModel.id == VehicleUnit.model_id)
        .where(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
    )
    if scoped_salesperson_id is not None:
        order_query = order_query.where(Order.salesperson_id == scoped_salesperson_id)
    order_rows = db.execute(order_query).all()

    return CustomerDetailResponse(
        customer=CustomerResponse.from_model(customer),
        rfm_segment=rfm_segment,
        recency_score=recency_score,
        frequency_score=frequency_score,
        monetary_score=monetary_score,
        orders=[
            CustomerOrderSummaryResponse(
                id=row.id,
                created_at=row.created_at,
                model_name=f"{row.make} {row.model}",
                negotiated_price=float(row.negotiated_price),
                status=row.status,
            )
            for row in order_rows
        ],
    )
