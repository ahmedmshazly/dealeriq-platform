"""Response models for the Manager/Sales dashboards (FR-050, FR-051)."""

import uuid
from datetime import date

from pydantic import BaseModel


class SalesVsForecastPointResponse(BaseModel):
    week_start: date
    actual: float
    yhat: float | None
    yhat_lo80: float | None
    yhat_hi80: float | None


class ModelRevenueResponse(BaseModel):
    model_id: uuid.UUID
    display_name: str
    revenue: float


class ManagerDashboardResponse(BaseModel):
    month: date
    sales_vs_forecast: list[SalesVsForecastPointResponse]
    top_models: list[ModelRevenueResponse]
    bottom_models: list[ModelRevenueResponse]
    inventory_abc_xyz_counts: dict[str, int]
    aging_unit_count: int
    open_anomaly_count: int
    unacknowledged_alert_count: int


class RankedLeadResponse(BaseModel):
    lead_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    model_id: uuid.UUID
    model_name: str
    status: str
    conversion_probability: float | None


class SalesDashboardResponse(BaseModel):
    open_leads: list[RankedLeadResponse]
    my_sales_this_month: float
    my_target: float
    unacknowledged_alert_count: int
