"""GET /dashboards/manager, GET /dashboards/sales (FR-050, FR-051)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.core.config import get_settings
from dealeriq_api.core.db import get_db
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.domain.models.vehicle import VehicleModel
from dealeriq_api.domain.services.dashboard_service import manager_dashboard, sales_dashboard
from dealeriq_api.schemas.dashboards import (
    ManagerDashboardResponse,
    ModelRevenueResponse,
    RankedLeadResponse,
    SalesDashboardResponse,
    SalesVsForecastPointResponse,
)

router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])


@router.get("/manager", response_model=ManagerDashboardResponse)
def manager_dashboard_route(
    current_user: User = Depends(require_permission("dashboard:view_manager")),
    db: Session = Depends(get_db),
) -> ManagerDashboardResponse:
    dashboard = manager_dashboard(db, current_user.id)
    return ManagerDashboardResponse(
        month=dashboard.month,
        sales_vs_forecast=[
            SalesVsForecastPointResponse(
                week_start=p.week_start,
                actual=p.actual,
                yhat=p.yhat,
                yhat_lo80=p.yhat_lo80,
                yhat_hi80=p.yhat_hi80,
            )
            for p in dashboard.sales_vs_forecast
        ],
        top_models=[
            ModelRevenueResponse(
                model_id=m.model_id, display_name=m.display_name, revenue=m.revenue
            )
            for m in dashboard.top_models
        ],
        bottom_models=[
            ModelRevenueResponse(
                model_id=m.model_id, display_name=m.display_name, revenue=m.revenue
            )
            for m in dashboard.bottom_models
        ],
        inventory_abc_xyz_counts=dashboard.inventory_abc_xyz_counts,
        aging_unit_count=dashboard.aging_unit_count,
        open_anomaly_count=dashboard.open_anomaly_count,
        unacknowledged_alert_count=dashboard.unacknowledged_alert_count,
    )


@router.get("/sales", response_model=SalesDashboardResponse)
def sales_dashboard_route(
    current_user: User = Depends(require_permission("dashboard:view_sales")),
    db: Session = Depends(get_db),
) -> SalesDashboardResponse:
    settings = get_settings()
    dashboard = sales_dashboard(
        db, current_user.id, default_target=settings.default_monthly_sales_target
    )

    customer_ids = {lead.customer_id for lead in dashboard.open_leads}
    model_ids = {lead.model_id for lead in dashboard.open_leads}
    customer_names = {
        row.id: row.name
        for row in db.execute(select(Customer).where(Customer.id.in_(customer_ids))).scalars()
    }
    model_names = {
        row.id: f"{row.make} {row.model}"
        for row in db.execute(select(VehicleModel).where(VehicleModel.id.in_(model_ids))).scalars()
    }

    return SalesDashboardResponse(
        open_leads=[
            RankedLeadResponse(
                lead_id=lead.lead_id,
                customer_id=lead.customer_id,
                customer_name=customer_names.get(lead.customer_id, "Unknown"),
                model_id=lead.model_id,
                model_name=model_names.get(lead.model_id, "Unknown"),
                status=lead.status,
                conversion_probability=lead.conversion_probability,
            )
            for lead in dashboard.open_leads
        ],
        my_sales_this_month=dashboard.my_sales_this_month,
        my_target=dashboard.my_target,
        unacknowledged_alert_count=dashboard.unacknowledged_alert_count,
    )
