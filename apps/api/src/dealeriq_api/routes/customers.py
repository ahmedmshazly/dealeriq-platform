"""GET/POST /customers (FR-030)."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.auth.schemas import Page
from dealeriq_api.core.db import get_db
from dealeriq_api.domain.customer_service import create_customer, list_customers
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.schemas.customers import (
    CustomerCreateRequest,
    CustomerCreateResponse,
    CustomerResponse,
)

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


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
