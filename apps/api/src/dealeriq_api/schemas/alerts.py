"""Request/response models for the alert notification center (FR-062, FR-063)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from dealeriq_api.domain.models.alerts import AlertSeverity, AlertStatus


class AlertResponse(BaseModel):
    id: uuid.UUID
    rule_key: str
    dedup_key: str
    severity: AlertSeverity
    payload: dict[str, Any]
    status: AlertStatus
    acknowledged_by: uuid.UUID | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime


class AlertListResponse(BaseModel):
    badge_count: int
    alerts: list[AlertResponse]


class AlertRuleResponse(BaseModel):
    key: str
    params: dict[str, Any]
    severity: AlertSeverity
    enabled: bool
    version: int


class AlertRuleUpdateRequest(BaseModel):
    params: dict[str, Any] | None = None
    severity: AlertSeverity | None = None
    enabled: bool | None = None
