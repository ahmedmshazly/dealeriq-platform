"""Days-on-lot tracking (DS-INV-003) and Kaplan-Meier survival analysis of time-to-sale
(DS-INV-004).

Kaplan-Meier (not a plain histogram of past sale times) is required here specifically because
of censoring: a unit still in stock hasn't "failed to sell" — it just hasn't sold *yet*, and its
true time-to-sale is unknown but at least its current age. Treating it as a fixed observation
(or dropping it) would silently bias the curve toward fast-moving stock, which is exactly the
population least in need of the pricing-review flag this feature exists to produce. `lifelines`
(ADR-017) handles this right-censoring natively via `event_observed=False`.
"""

import dataclasses
from datetime import date

import numpy as np
from lifelines import KaplanMeierFitter

SALE_PROBABILITY_HORIZON_DAYS = 30
WORST_DECILE_PERCENTILE = 10.0


def days_on_lot(acquisition_date: date, as_of: date) -> int:
    return (as_of - acquisition_date).days


def is_aging(days: int, threshold_days: int) -> bool:
    return days >= threshold_days


@dataclasses.dataclass(frozen=True)
class TimeToSaleObservation:
    unit_id: str
    duration_days: int
    """Days from acquisition to sale (if sold) or to `as_of` (if still in stock)."""
    sold: bool
    """True = observed sale (uncensored). False = still in stock as of the run (right-censored)."""


def fit_survival_curve(observations: list[TimeToSaleObservation]) -> KaplanMeierFitter:
    kmf = KaplanMeierFitter()
    durations = [o.duration_days for o in observations]
    event_observed = [o.sold for o in observations]
    kmf.fit(durations=durations, event_observed=event_observed)
    return kmf


def sale_probability_within(
    kmf: KaplanMeierFitter, current_age_days: int, horizon_days: int = SALE_PROBABILITY_HORIZON_DAYS
) -> float:
    """Conditional probability of selling within `horizon_days`, given survival to
    `current_age_days` already: `1 - S(age+horizon)/S(age)`. If `S(age)` is already 0 (no unit in
    the fitted population survived this long), the conditional probability is undefined by the
    curve — treated as 0.0 (no further evidence this unit will sell soon) rather than raising,
    since this is a real, reachable state for an old outlier unit, not a bug."""
    s_now = float(kmf.predict(current_age_days))
    if s_now <= 0.0:
        return 0.0
    s_future = float(kmf.predict(current_age_days + horizon_days))
    return max(0.0, min(1.0, 1.0 - s_future / s_now))


def worst_decile_threshold(probabilities: list[float]) -> float:
    """The sale-probability value at the `WORST_DECILE_PERCENTILE`th percentile — units at or
    below it are the least likely to sell soon and get flagged for pricing review. Uses linear
    interpolation between closest ranks (numpy's default), the standard percentile convention."""
    return float(np.percentile(np.array(probabilities, dtype=float), WORST_DECILE_PERCENTILE))
