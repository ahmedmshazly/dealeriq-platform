"""Request/response models for customers (FR-030)."""

import uuid

from pydantic import BaseModel

from dealeriq_api.domain.models.customer import Customer


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
