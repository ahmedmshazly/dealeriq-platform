"""The six FR-061 built-in alert rules, plus the shared dedup/fan-out helper (FR-062, FR-063).

Deliberately in `apps/api`'s domain layer, not `packages/analytics` (spec.md's Assumptions):
every rule here is a DB read against already-computed Phase 4/5 outputs compared to a configured
threshold — there is no meaningful DB-free "pure" version of "is this row's value below that
row's value," unlike Phases 4-5's genuine statistical computation.

Rules (a)-(d) and (f) are evaluated by `alert_job.py` after an analytics run; rule (e) is called
directly from `order_service.submit_order` (FR-060's "transactional trigger" case).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dealeriq_api.domain.models.alerts import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    Notification,
)
from dealeriq_api.domain.models.analytics import Forecast
from dealeriq_api.domain.models.inventory_intel import Anomaly, InventoryIntel, UnitRisk
from dealeriq_api.domain.models.lead import Lead, LeadStatus
from dealeriq_api.domain.models.order import Order
from dealeriq_api.domain.models.rbac import Role, User
from dealeriq_api.domain.models.vehicle import UnitStatus, VehicleUnit

NOTIFICATION_CHANNEL_IN_APP = "in_app"


def _get_rule(db: Session, key: str) -> AlertRule | None:
    rule = db.execute(select(AlertRule).where(AlertRule.key == key)).scalar_one_or_none()
    if rule is None or not rule.enabled:
        return None
    return rule


def open_alert(
    db: Session,
    *,
    rule_key: str,
    dedup_key: str,
    severity: AlertSeverity,
    payload: dict[str, object],
) -> Alert | None:
    """Conditional insert: no duplicate *open-or-acknowledged* alert for the same
    (rule_key, dedup_key) (FR-062). Returns `None` (not an error) when one already exists —
    that's the expected, common case on a repeat evaluation, not a failure."""
    existing = db.execute(
        select(Alert.id).where(
            Alert.rule_key == rule_key,
            Alert.dedup_key == dedup_key,
            Alert.status != AlertStatus.RESOLVED,
        )
    ).first()
    if existing is not None:
        return None

    alert = Alert(
        rule_key=rule_key,
        dedup_key=dedup_key,
        severity=severity,
        payload=payload,
        status=AlertStatus.OPEN,
    )
    db.add(alert)
    db.flush()
    _fan_out_notifications(db, alert, rule_key)
    return alert


def _fan_out_notifications(db: Session, alert: Alert, rule_key: str) -> None:
    rule = _get_rule(db, rule_key)
    subscribed_roles: list[str] = rule.params.get("subscribed_roles", []) if rule else []
    if not subscribed_roles:
        return
    users = (
        db.execute(
            select(User).join(Role, Role.id == User.role_id).where(Role.key.in_(subscribed_roles))
        )
        .scalars()
        .all()
    )
    for user in users:
        db.add(
            Notification(user_id=user.id, alert_id=alert.id, channel=NOTIFICATION_CHANNEL_IN_APP)
        )


def _on_hand_count(db: Session, model_id: uuid.UUID, branch_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count())
        .select_from(VehicleUnit)
        .where(
            VehicleUnit.model_id == model_id,
            VehicleUnit.branch_id == branch_id,
            VehicleUnit.status.in_([UnitStatus.IN_STOCK, UnitStatus.RESERVED]),
        )
    ).scalar_one()


def evaluate_stock_reorder(db: Session, inventory_run_id: uuid.UUID) -> int:
    """Rule (a): on-hand stock at or below Phase 5's persisted reorder point."""
    rule = _get_rule(db, "stock_reorder")
    if rule is None:
        return 0
    rows = (
        db.execute(
            select(InventoryIntel).where(
                InventoryIntel.run_id == inventory_run_id,
                InventoryIntel.reorder_point.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    count = 0
    for row in rows:
        on_hand = _on_hand_count(db, row.model_id, row.branch_id)
        assert row.reorder_point is not None  # filtered by the query above
        if on_hand <= row.reorder_point:
            dedup_key = f"model:{row.model_id}::branch:{row.branch_id}"
            alert = open_alert(
                db,
                rule_key="stock_reorder",
                dedup_key=dedup_key,
                severity=rule.severity,
                payload={
                    "model_id": str(row.model_id),
                    "branch_id": str(row.branch_id),
                    "on_hand": on_hand,
                    "reorder_point": row.reorder_point,
                },
            )
            if alert is not None:
                count += 1
    return count


def evaluate_unit_aging(db: Session, inventory_run_id: uuid.UUID) -> int:
    """Rule (b): surfaces Phase 5's own `is_aging` flag directly."""
    rule = _get_rule(db, "unit_aging")
    if rule is None:
        return 0
    rows = (
        db.execute(
            select(UnitRisk).where(UnitRisk.run_id == inventory_run_id, UnitRisk.is_aging.is_(True))
        )
        .scalars()
        .all()
    )
    count = 0
    for row in rows:
        alert = open_alert(
            db,
            rule_key="unit_aging",
            dedup_key=f"unit:{row.unit_id}",
            severity=rule.severity,
            payload={"unit_id": str(row.unit_id), "days_on_lot": row.days_on_lot},
        )
        if alert is not None:
            count += 1
    return count


def _map_anomaly_severity(score: float) -> AlertSeverity:
    """DS-ANO-004's stated hand-off: this rule's severity comes from the anomaly's own score,
    not a second, independently-invented scale. Bucketed at the same z-score-adjacent breakpoints
    `packages/analytics/anomalies_detector/series_anomalies.py`'s severity computation uses
    (severity = min(|z|/3.5, 5.0), so a raw score >= 3.0 corresponds to |z| well past the
    detection threshold)."""
    if score >= 3.0:
        return AlertSeverity.CRITICAL
    if score >= 1.5:
        return AlertSeverity.WARNING
    return AlertSeverity.INFO


def evaluate_sales_anomaly(db: Session, inventory_run_id: uuid.UUID) -> int:
    """Rule (c): one alert per newly-detected anomaly."""
    rule = _get_rule(db, "sales_anomaly")
    if rule is None:
        return 0
    rows = (
        db.execute(
            select(Anomaly).where(Anomaly.run_id == inventory_run_id, Anomaly.status == "new")
        )
        .scalars()
        .all()
    )
    count = 0
    for row in rows:
        dedup_key = f"{row.scope}:{row.entity_key}:{row.week_start or ''}"
        alert = open_alert(
            db,
            rule_key="sales_anomaly",
            dedup_key=dedup_key,
            severity=_map_anomaly_severity(row.severity),
            payload={
                "scope": row.scope,
                "entity_key": row.entity_key,
                "observed": row.observed,
                "expected": row.expected,
                "score": row.score,
                "method": row.method,
            },
        )
        if alert is not None:
            count += 1
    return count


def evaluate_forecast_stockout(db: Session, forecast_run_id: uuid.UUID) -> int:
    """Rule (d): on-hand stock vs. the champion forecast's point-estimate demand over the
    lead-time window — a distinct, more urgent signal than rule (a): even *expected* demand
    (not the quantile-inflated reorder point) would exhaust current stock."""
    rule = _get_rule(db, "forecast_stockout")
    if rule is None:
        return 0
    lead_time_weeks = int(rule.params.get("lead_time_weeks", 2))

    rows = (
        db.execute(
            select(Forecast)
            .where(Forecast.run_id == forecast_run_id, Forecast.series_key.like("model:%"))
            .order_by(Forecast.series_key, Forecast.week_start)
        )
        .scalars()
        .all()
    )
    by_series: dict[str, list[Forecast]] = {}
    for row in rows:
        by_series.setdefault(row.series_key, []).append(row)

    count = 0
    for series_key, points in by_series.items():
        window = points[:lead_time_weeks]
        if len(window) < lead_time_weeks:
            continue
        expected_demand = sum(p.yhat for p in window)
        parts = series_key.split("::")
        model_id = uuid.UUID(parts[0].removeprefix("model:"))
        branch_id = uuid.UUID(parts[1].removeprefix("branch:"))
        on_hand = _on_hand_count(db, model_id, branch_id)
        if on_hand < expected_demand:
            alert = open_alert(
                db,
                rule_key="forecast_stockout",
                dedup_key=series_key,
                severity=rule.severity,
                payload={
                    "series_key": series_key,
                    "on_hand": on_hand,
                    "expected_demand": expected_demand,
                    "lead_time_weeks": lead_time_weeks,
                },
            )
            if alert is not None:
                count += 1
    return count


def evaluate_lead_idle(db: Session, *, as_of: datetime | None = None) -> int:
    """Rule (f): idle-days only this phase — the score-cutoff half is deferred to Phase 7
    (spec.md Assumptions), since DS-CUST lead scoring doesn't exist yet."""
    rule = _get_rule(db, "lead_idle")
    if rule is None:
        return 0
    as_of = as_of or datetime.now(UTC)
    threshold_days = int(rule.params.get("idle_days_threshold", 14))
    cutoff = as_of - timedelta(days=threshold_days)

    rows = (
        db.execute(
            select(Lead).where(
                Lead.status.notin_([LeadStatus.WON, LeadStatus.LOST]),
                Lead.last_activity_at < cutoff,
            )
        )
        .scalars()
        .all()
    )
    count = 0
    for lead in rows:
        idle_days = (as_of - lead.last_activity_at).days
        alert = open_alert(
            db,
            rule_key="lead_idle",
            dedup_key=f"lead:{lead.id}",
            severity=rule.severity,
            payload={"lead_id": str(lead.id), "idle_days": idle_days},
        )
        if alert is not None:
            count += 1
    return count


def evaluate_discount_approval(db: Session, order: Order, fraction: float) -> Alert | None:
    """Rule (e): the one FR-061 rule evaluated transactionally (FR-060), inline in
    `order_service.submit_order` — reuses the exact same `fraction` comparison that already
    decided the manager-approval requirement, so the alert and the approval can never drift
    apart."""
    rule = _get_rule(db, "discount_approval")
    if rule is None:
        return None
    return open_alert(
        db,
        rule_key="discount_approval",
        dedup_key=f"order:{order.id}",
        severity=rule.severity,
        payload={"order_id": str(order.id), "discount_fraction": fraction},
    )
