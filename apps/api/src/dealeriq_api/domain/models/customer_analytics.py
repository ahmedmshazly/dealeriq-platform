"""CustomerRfmProfile, LeadScore - Phase 7's analytics tables (DS-CUST-001..005). Schema follows
Phase 4/5's exact convention: `run_id`-tagged output tables, never mutating `customers`/`leads`
in place (DAT-003). Callers always resolve the latest succeeded `job_name="lead_scoring"` run
first, then join these tables by `run_id`, matching `forecasts`/`inventory_intel`'s own lookup
pattern.
"""

import uuid

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dealeriq_api.domain.base import Base, IdMixin


class CustomerRfmProfile(IdMixin, Base):
    __tablename__ = "customer_rfm_profiles"
    __table_args__ = (
        Index("ix_customer_rfm_profiles_run_id_customer_id", "run_id", "customer_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics_runs.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    recency_score: Mapped[int | None] = mapped_column(default=None)
    frequency_score: Mapped[int | None] = mapped_column(default=None)
    monetary_score: Mapped[int | None] = mapped_column(default=None)
    segment: Mapped[str] = mapped_column(String(30))
    """One of ADR-022's five segment names ("New" when the score columns above are all null)."""


class LeadScore(IdMixin, Base):
    __tablename__ = "lead_scores"
    __table_args__ = (Index("ix_lead_scores_run_id_lead_id", "run_id", "lead_id"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics_runs.id"))
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    conversion_probability: Mapped[float] = mapped_column(Float)
    top_features: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    """DS-CUST-004: `[{"label": str, "contribution": float}, ...]`, at most 3 entries, sorted
    descending by `abs(contribution)`."""
