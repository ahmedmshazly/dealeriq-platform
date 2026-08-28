"""RFM segmentation (DS-CUST-001): Recency/Frequency/Monetary quintile scoring, mapped to a
named behavioral segment per ADR-022's five-segment table.

Quintiles are population-relative (computed fresh against whichever customers are passed in,
per run), not fixed global thresholds - standard RFM practice. Customers with zero delivered
orders skip quintile scoring entirely (Recency/Frequency/Monetary are undefined without at
least one transaction) and are assigned the `"New"` segment directly rather than a fabricated
quintile score, per spec.md's Edge Cases.
"""

import dataclasses

import numpy as np
import pandas as pd

SEGMENT_NEW = "New"
SEGMENT_CHAMPIONS = "Champions"
SEGMENT_LOYAL = "Loyal Customers"
SEGMENT_AT_RISK = "At Risk"
SEGMENT_HIBERNATING = "Hibernating"


@dataclasses.dataclass(frozen=True)
class CustomerOrderStats:
    customer_id: str
    recency_days: float
    frequency: int
    monetary: float


@dataclasses.dataclass(frozen=True)
class RfmResult:
    customer_id: str
    recency_score: int | None
    frequency_score: int | None
    monetary_score: int | None
    segment: str


def _quintile_scores(values: pd.Series, *, higher_is_better: bool) -> pd.Series:
    """Rank-based quintile scoring (1-5, 5 = best) that never fails on duplicate values or a
    small population - unlike `pd.qcut`, which raises on duplicate bin edges whenever many
    customers share the same raw value (e.g. `frequency=1`, extremely common). Ties are broken
    by stable rank order (`method="first"`) over the caller's own row order, so the result is
    deterministic given a deterministic input ordering."""
    n = len(values)
    if n == 0:
        return pd.Series([], dtype="int64")
    ranks = values.rank(method="first", ascending=True)
    percentile = (ranks - 1) / max(n - 1, 1)
    bin_idx = np.minimum((percentile * 5).astype(int), 4)
    score = bin_idx + 1
    if not higher_is_better:
        score = 6 - score
    return score.astype("int64")


def _segment_for(recency_score: int, frequency_score: int, monetary_score: int) -> str:
    """ADR-022's four ordered rules - first match wins. At Risk is checked before Loyal: a
    customer who was frequent/high-value but hasn't bought recently (low R) is more usefully
    flagged as churn-risk than as "loyal" - recency is the more urgent signal for a Manager to
    see, since "loyal" implies ongoing engagement that a low R score contradicts."""
    if recency_score >= 4 and frequency_score >= 4 and monetary_score >= 4:
        return SEGMENT_CHAMPIONS
    if recency_score <= 2 and (frequency_score >= 3 or monetary_score >= 3):
        return SEGMENT_AT_RISK
    if frequency_score >= 4:
        return SEGMENT_LOYAL
    return SEGMENT_HIBERNATING


def compute_rfm(stats_by_customer: dict[str, CustomerOrderStats]) -> dict[str, RfmResult]:
    """Customers with `frequency == 0` (never completed an order) are split out before quintile
    scoring runs at all, so a population of "New" customers can never distort the quintile
    boundaries computed for customers who do have purchase history."""
    new_ids = [cid for cid, s in stats_by_customer.items() if s.frequency == 0]
    scored_ids = [cid for cid, s in stats_by_customer.items() if s.frequency > 0]

    results: dict[str, RfmResult] = {
        cid: RfmResult(
            customer_id=cid,
            recency_score=None,
            frequency_score=None,
            monetary_score=None,
            segment=SEGMENT_NEW,
        )
        for cid in new_ids
    }

    if not scored_ids:
        return results

    df = pd.DataFrame(
        [
            {
                "customer_id": cid,
                "recency_days": stats_by_customer[cid].recency_days,
                "frequency": stats_by_customer[cid].frequency,
                "monetary": stats_by_customer[cid].monetary,
            }
            for cid in scored_ids
        ]
    )
    df["recency_score"] = _quintile_scores(df["recency_days"], higher_is_better=False)
    df["frequency_score"] = _quintile_scores(df["frequency"], higher_is_better=True)
    df["monetary_score"] = _quintile_scores(df["monetary"], higher_is_better=True)

    for row in df.itertuples(index=False):
        segment = _segment_for(row.recency_score, row.frequency_score, row.monetary_score)
        results[row.customer_id] = RfmResult(
            customer_id=row.customer_id,
            recency_score=int(row.recency_score),
            frequency_score=int(row.frequency_score),
            monetary_score=int(row.monetary_score),
            segment=segment,
        )

    return results
