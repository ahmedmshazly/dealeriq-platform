"""Customer analytics job orchestration (DS-CUST-001..005, FR-074): RFM segmentation, then a
calibrated lead-conversion model trained fresh on this run's own resolved leads, then a PSI
drift check comparing this run's own training population against its own scoring population
(ADR-023 - no cross-run persisted baseline). Reads customers/orders/leads/lead_events, calls
`dealeriq_analytics.customer` (pure, DB-free computation), and writes run/customer_rfm_profiles/
lead_scores - reusing the shared `AnalyticsRun` run-tracking table (FR-070), mirroring
`inventory_job.py`'s exact `running -> succeeded/failed` lifecycle.

RFM must compute before lead scoring within the same run: a lead's `customer_rfm_score` feature
is this run's own fresh RFM output, not a stale value from an earlier run.
"""

import importlib.metadata
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_analytics.customer.lead_scoring import (
    CHANNEL_BASELINE,
    PSI_MONITORED_FEATURES,
    LeadFeatureRow,
    ScoredLead,
    train_and_score,
)
from dealeriq_analytics.customer.psi import PSI_DRIFT_THRESHOLD, compute_psi_report
from dealeriq_analytics.customer.rfm import CustomerOrderStats, RfmResult, compute_rfm
from dealeriq_api.domain.alerts.alert_rules import evaluate_lead_score_drift
from dealeriq_api.domain.jobs.job_lifecycle import begin_run
from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus
from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.models.customer_analytics import CustomerRfmProfile, LeadScore
from dealeriq_api.domain.models.lead import Lead, LeadEvent, LeadStatus
from dealeriq_api.domain.models.order import Order, OrderStatus
from dealeriq_api.domain.models.vehicle import VehicleModel

JOB_NAME = "lead_scoring"


def _code_version() -> str:
    try:
        return importlib.metadata.version("dealeriq-analytics")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _load_customer_order_stats(db: Session, as_of: datetime) -> dict[str, CustomerOrderStats]:
    customer_ids = db.execute(select(Customer.id)).scalars().all()
    order_rows = db.execute(
        select(Order.customer_id, Order.negotiated_price, Order.created_at).where(
            Order.status == OrderStatus.DELIVERED
        )
    ).all()

    orders_by_customer: dict[uuid.UUID, list[tuple[float, datetime]]] = {}
    for row in order_rows:
        orders_by_customer.setdefault(row.customer_id, []).append(
            (float(row.negotiated_price), row.created_at)
        )

    stats: dict[str, CustomerOrderStats] = {}
    for customer_id in customer_ids:
        rows = orders_by_customer.get(customer_id, [])
        if not rows:
            stats[str(customer_id)] = CustomerOrderStats(
                customer_id=str(customer_id), recency_days=0.0, frequency=0, monetary=0.0
            )
            continue
        last_order_at = max(created_at for _, created_at in rows)
        recency_days = max((as_of - last_order_at).total_seconds() / 86400.0, 0.0)
        stats[str(customer_id)] = CustomerOrderStats(
            customer_id=str(customer_id),
            recency_days=recency_days,
            frequency=len(rows),
            monetary=sum(price for price, _ in rows),
        )
    return stats


def _customer_rfm_score(result: RfmResult | None) -> float | None:
    if result is None or result.recency_score is None:
        return None
    assert result.frequency_score is not None and result.monetary_score is not None
    return (result.recency_score + result.frequency_score + result.monetary_score) / 3.0


INTERACTION_COUNT_WINDOW_DAYS = 21
"""`LeadEvent` only records status-transition events (Phase 2), and Phase 3's seed generator
walks each lead's funnel with a path *length* that already depends on the ground-truth won/lost
outcome (a won lead always completes the full new -> ... -> won path; a lost lead has a 40%
chance of an early exit at every step), so counting a resolved lead's *entire* event history
would leak the outcome back in as a feature (more events almost always means "won", not because
more engagement caused the win, but because the generator's own branching already knew the
answer). Bounding the count to events within this many days of creation keeps the feature to
information that would genuinely have been available while the lead was still open, for both
historical (training) and currently-open (scoring) leads alike."""


def _load_lead_feature_rows(
    db: Session, rfm_by_customer: dict[str, RfmResult]
) -> list[LeadFeatureRow]:
    lead_rows = db.execute(
        select(
            Lead.id,
            Lead.customer_id,
            Lead.budget_band,
            Lead.status,
            Lead.created_at,
            Customer.source_channel,
            VehicleModel.segment,
        )
        .join(Customer, Customer.id == Lead.customer_id)
        .join(VehicleModel, VehicleModel.id == Lead.model_id)
    ).all()
    event_rows = db.execute(select(LeadEvent.lead_id, LeadEvent.at)).all()
    events_by_lead_id: dict[uuid.UUID, list[datetime]] = {}
    for event_lead_id, at in event_rows:
        events_by_lead_id.setdefault(event_lead_id, []).append(at)

    rows: list[LeadFeatureRow] = []
    for row in lead_rows:
        won: bool | None = None
        if row.status == LeadStatus.WON:
            won = True
        elif row.status == LeadStatus.LOST:
            won = False
        rfm_result = rfm_by_customer.get(str(row.customer_id))
        window_end = row.created_at + timedelta(days=INTERACTION_COUNT_WINDOW_DAYS)
        interaction_count = sum(1 for at in events_by_lead_id.get(row.id, []) if at <= window_end)
        rows.append(
            LeadFeatureRow(
                lead_id=str(row.id),
                channel=row.source_channel or CHANNEL_BASELINE,
                budget_band=row.budget_band,
                model_segment=row.segment,
                created_at=row.created_at,
                interaction_count=interaction_count,
                customer_rfm_score=_customer_rfm_score(rfm_result),
                won=won,
            )
        )
    return rows


def run_lead_scoring_job(db: Session) -> AnalyticsRun:
    run = begin_run(db, job_name=JOB_NAME, code_version=_code_version())

    try:
        summary = _execute_pipeline(db, run.id)
        run.status = RunStatus.SUCCEEDED
        run.finished_at = datetime.now(UTC)
        run.metrics = summary
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.metrics = {"error": str(exc)}
        db.commit()
        raise

    db.commit()
    db.refresh(run)
    return run


def _execute_pipeline(db: Session, run_id: uuid.UUID) -> dict[str, object]:
    as_of = datetime.now(UTC)

    order_stats = _load_customer_order_stats(db, as_of)
    rfm_by_customer = compute_rfm(order_stats)
    n_rfm = _write_customer_rfm(db, run_id, rfm_by_customer)

    lead_rows = _load_lead_feature_rows(db, rfm_by_customer)
    resolved_rows = [r for r in lead_rows if r.won is not None]
    open_rows = [r for r in lead_rows if r.won is None]

    result = train_and_score(resolved_rows, open_rows, as_of=as_of)
    n_scored = _write_lead_scores(db, run_id, result.scored)

    drift_report = {}
    if len(result.score_features) > 0:
        drift_report = compute_psi_report(
            result.train_features, result.score_features, list(PSI_MONITORED_FEATURES)
        )
    drifted_features = {k: v for k, v in drift_report.items() if v > PSI_DRIFT_THRESHOLD}
    evaluate_lead_score_drift(db, run_id, drifted_features)

    return {
        "customer_rfm_profiles": n_rfm,
        "lead_scores": n_scored,
        "roc_auc": result.metrics.roc_auc,
        "pr_auc": result.metrics.pr_auc,
        "brier_score": result.metrics.brier_score,
        "n_train": result.metrics.n_train,
        "n_validate": result.metrics.n_validate,
        "drifted_features": drifted_features,
    }


def _write_customer_rfm(
    db: Session, run_id: uuid.UUID, rfm_by_customer: dict[str, RfmResult]
) -> int:
    count = 0
    for customer_id_str, result in rfm_by_customer.items():
        db.add(
            CustomerRfmProfile(
                run_id=run_id,
                customer_id=uuid.UUID(customer_id_str),
                recency_score=result.recency_score,
                frequency_score=result.frequency_score,
                monetary_score=result.monetary_score,
                segment=result.segment,
            )
        )
        count += 1
    return count


def _write_lead_scores(db: Session, run_id: uuid.UUID, scored: list[ScoredLead]) -> int:
    count = 0
    for lead in scored:
        db.add(
            LeadScore(
                run_id=run_id,
                lead_id=uuid.UUID(lead.lead_id),
                conversion_probability=lead.conversion_probability,
                top_features=[
                    {"label": f.label, "contribution": f.contribution} for f in lead.top_features
                ],
            )
        )
        count += 1
    return count
