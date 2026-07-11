"""Request/response models for customers (FR-030, FR-033)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.order import OrderStatus


class CustomerCreateRequest(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    source_channel: str | None = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    city: str | None
    source_channel: str | None

    @classmethod
    def from_model(cls, customer: Customer) -> "CustomerResponse":
        return cls(
            id=customer.id,
            name=customer.name,
            phone=customer.phone,
            email=customer.email,
            city=customer.city,
            source_channel=customer.source_channel,
        )


class CustomerCreateResponse(BaseModel):
    customer: CustomerResponse
    possible_duplicate_ids: list[uuid.UUID]


class CustomerOrderSummaryResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    model_name: str
    negotiated_price: float
    status: OrderStatus


class CustomerDetailResponse(BaseModel):
    customer: CustomerResponse
    # FR-033: null until the customer-analytics job has run at least once, or for a customer
    # with zero delivered orders (ADR-022's "New" segment carries no quintile scores).
    rfm_segment: str | None = None
    recency_score: int | None = None
    frequency_score: int | None = None
    monetary_score: int | None = None
    orders: list[CustomerOrderSummaryResponse] = []
