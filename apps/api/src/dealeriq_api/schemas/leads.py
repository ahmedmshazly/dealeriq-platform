"""Request/response models for leads (FR-031/032)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from dealeriq_api.domain.models.lead import Lead, LeadStatus


class LeadCreateRequest(BaseModel):
    customer_id: uuid.UUID
    model_id: uuid.UUID
    budget_band: str
    owner_id: uuid.UUID


class LeadTransitionRequest(BaseModel):
    target_status: LeadStatus
    notes: str | None = None


class FeatureContributionResponse(BaseModel):
    label: str
    contribution: float


class LeadResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    model_id: uuid.UUID
    budget_band: str
    status: LeadStatus
    owner_id: uuid.UUID
    last_activity_at: datetime
    # Analytics outputs (DS-CUST, Phase 7) - null until the lead-scoring job has run for this lead.
    conversion_probability: float | None = None
    rfm_segment: str | None = None
    top_features: list[FeatureContributionResponse] = []

    @classmethod
    def from_model(
        cls,
        lead: Lead,
        *,
        conversion_probability: float | None = None,
        rfm_segment: str | None = None,
        top_features: list[FeatureContributionResponse] | None = None,
    ) -> "LeadResponse":
        return cls(
            id=lead.id,
            customer_id=lead.customer_id,
            model_id=lead.model_id,
            budget_band=lead.budget_band,
            status=lead.status,
            owner_id=lead.owner_id,
            last_activity_at=lead.last_activity_at,
            conversion_probability=conversion_probability,
            rfm_segment=rfm_segment,
            top_features=top_features or [],
        )
