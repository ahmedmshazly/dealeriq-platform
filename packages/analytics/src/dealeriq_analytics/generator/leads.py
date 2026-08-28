"""Lead funnel logit simulation (GEN-003). Pure numpy - no DB dependency.

logit(P(won)) = gamma0 + gamma_channel[source] + gamma_budget*budget_level +
                gamma_segment[model_segment] + gamma_days*days_since_creation +
                gamma_interactions*interaction_count + gamma_rfm*customer_rfm_quintile +
                gamma_season*is_peak_season

The five coefficient groups explicitly pinned by specs/004-synthetic-data/plan.md (channel,
budget's *existence* as a feature, days-since-creation, interaction count, RFM quintile, and
economy-vs-luxury for segment) are marked below. Plan.md's prose didn't give exact values for the
intercept, the non-economy segment levels, the per-level budget slope, or a seasonal term - those
are filled in here as reasonable, documented defaults (see phase report
03-synthetic-data.md's deviations section), chosen so every coefficient still has an
unambiguous, recoverable sign for SC-003's logistic-regression sign-recovery check.

RFM quintile is generated as an exogenous input here, not derived from a customer's real order
history - GEN-003 is explicitly "simulated independently from the order/demand realization"
(plan.md), so the pure-stats layer treats it as one more drawn feature. The seed-time orchestrator
(infra/seed) is what ties simulated leads to real Customer/Order rows.
"""

import dataclasses

import numpy as np
from numpy.typing import NDArray

CHANNELS: tuple[str, ...] = ("referral", "walk_in", "web_form", "phone", "social_ad")
GAMMA_CHANNEL: dict[str, float] = {
    "referral": 0.8,  # plan.md
    "walk_in": 0.3,  # plan.md
    "web_form": 0.0,  # plan.md baseline
    "phone": -0.2,  # plan.md
    "social_ad": -0.5,  # plan.md
}

BUDGET_BANDS: tuple[str, ...] = ("under_20k", "20k_35k", "35k_55k", "55k_plus")
GAMMA_BUDGET_PER_LEVEL = 0.15
"""Not specified in plan.md. Documented default: a higher declared budget band signals a more
qualified, financing-ready buyer, so the slope is positive."""

SEGMENTS: tuple[str, ...] = ("economy", "sedan", "suv_truck", "commercial", "luxury")
GAMMA_SEGMENT: dict[str, float] = {
    "economy": 0.4,  # plan.md: "economy-segment +0.4 vs luxury baseline"
    "sedan": 0.3,  # documented default: mainstream segment, shorter decision cycle
    "suv_truck": 0.2,  # documented default
    "commercial": 0.1,  # documented default: closer to luxury's longer B2B cycle
    "luxury": 0.0,  # plan.md baseline
}

GAMMA_DAYS_SINCE_CREATION = -0.02  # plan.md: -0.02/day
GAMMA_INTERACTION_COUNT = 0.25  # plan.md: +0.25/interaction
GAMMA_RFM_QUINTILE = 0.3  # plan.md: +0.3/quintile
GAMMA_SEASON = 0.15
"""Not specified in plan.md. Documented default: leads created during the spring/summer peak
buying season convert somewhat more often."""
GAMMA_INTERCEPT = -1.5
"""Not specified in plan.md. Documented default, calibrated so a lead with baseline features
(web-form, lowest budget/RFM, luxury segment, no interactions, off-season) has a realistic ~18%
P(won), rising well above that as positive features accumulate."""

PEAK_SEASON_WEEKS = frozenset(range(13, 40))


@dataclasses.dataclass(frozen=True)
class LeadCoefficients:
    intercept: float
    channel: dict[str, float]
    budget_per_level: float
    segment: dict[str, float]
    days_since_creation: float
    interaction_count: float
    rfm_quintile: float
    season: float


def ground_truth_coefficients() -> LeadCoefficients:
    return LeadCoefficients(
        intercept=GAMMA_INTERCEPT,
        channel=dict(GAMMA_CHANNEL),
        budget_per_level=GAMMA_BUDGET_PER_LEVEL,
        segment=dict(GAMMA_SEGMENT),
        days_since_creation=GAMMA_DAYS_SINCE_CREATION,
        interaction_count=GAMMA_INTERACTION_COUNT,
        rfm_quintile=GAMMA_RFM_QUINTILE,
        season=GAMMA_SEASON,
    )


@dataclasses.dataclass(frozen=True)
class SimulatedLead:
    lead_key: str
    channel: str
    budget_band: str
    budget_level: int
    segment: str
    days_since_creation: int
    interaction_count: int
    rfm_quintile: int
    creation_week: int
    is_peak_season: bool
    p_won: float
    won: bool


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def simulate_leads(
    n_leads: int,
    n_weeks: int,
    rng: np.random.Generator,
    segments: tuple[str, ...] = SEGMENTS,
) -> list[SimulatedLead]:
    coeffs = ground_truth_coefficients()
    leads: list[SimulatedLead] = []
    for i in range(n_leads):
        channel = str(rng.choice(np.array(CHANNELS)))
        budget_level = int(rng.integers(0, len(BUDGET_BANDS)))
        segment = str(rng.choice(np.array(segments)))
        days_since_creation = int(rng.integers(0, 90))
        interaction_count = int(rng.poisson(2.0))
        rfm_quintile = int(rng.integers(1, 6))
        creation_week = int(rng.integers(0, n_weeks))
        is_peak_season = (creation_week % 52) in PEAK_SEASON_WEEKS

        logit = (
            coeffs.intercept
            + coeffs.channel[channel]
            + coeffs.budget_per_level * budget_level
            + coeffs.segment[segment]
            + coeffs.days_since_creation * days_since_creation
            + coeffs.interaction_count * interaction_count
            + coeffs.rfm_quintile * rfm_quintile
            + coeffs.season * float(is_peak_season)
        )
        p_won = _sigmoid(logit)
        won = bool(rng.uniform() < p_won)

        leads.append(
            SimulatedLead(
                lead_key=f"lead-{i:06d}",
                channel=channel,
                budget_band=BUDGET_BANDS[budget_level],
                budget_level=budget_level,
                segment=segment,
                days_since_creation=days_since_creation,
                interaction_count=interaction_count,
                rfm_quintile=rfm_quintile,
                creation_week=creation_week,
                is_peak_season=is_peak_season,
                p_won=p_won,
                won=won,
            )
        )
    return leads


def leads_to_design_matrix(
    leads: list[SimulatedLead],
) -> tuple[NDArray[np.float64], NDArray[np.int64], list[str]]:
    """Encodes simulated leads into an (X, y, feature_names) design matrix suitable for fitting a
    logistic regression - used by the sign-recovery validation test (SC-003)."""
    feature_names = (
        [f"channel__{c}" for c in CHANNELS if c != "web_form"]
        + [
            "budget_level",
        ]
        + [f"segment__{s}" for s in SEGMENTS if s != "luxury"]
        + [
            "days_since_creation",
            "interaction_count",
            "rfm_quintile",
            "is_peak_season",
        ]
    )

    rows: list[list[float]] = []
    outcomes: list[int] = []
    for lead in leads:
        row = [1.0 if lead.channel == c else 0.0 for c in CHANNELS if c != "web_form"]
        row.append(float(lead.budget_level))
        row.extend(1.0 if lead.segment == s else 0.0 for s in SEGMENTS if s != "luxury")
        row.append(float(lead.days_since_creation))
        row.append(float(lead.interaction_count))
        row.append(float(lead.rfm_quintile))
        row.append(1.0 if lead.is_peak_season else 0.0)
        rows.append(row)
        outcomes.append(1 if lead.won else 0)

    return np.array(rows, dtype=np.float64), np.array(outcomes, dtype=np.int64), feature_names
