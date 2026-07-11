"""Lead-conversion scoring (DS-CUST-002..005, ADR-023): calibrated logistic regression with
per-lead top-3 explanations. Pure, DB-free — plain records in, dataclasses out (Phase 4/5's
established `packages/analytics` convention); no SQLAlchemy imports.

Two separate fits share one standardized feature matrix: a plain `LogisticRegression` supplies
interpretable coefficients for DS-CUST-004's top-3 explanations, and a `CalibratedClassifierCV`
wrapping the same estimator type supplies the calibrated probability actually shown to users
(DS-CUST-003) — `CalibratedClassifierCV` internally cross-validates and holds multiple fold
models, so there is no single clean coefficient vector to explain from directly. Both are fit on
the identical training rows and feature columns, so the explanation's direction/ranking stays
representative of what actually drove the calibrated score.
"""

import dataclasses
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

CHANNELS: tuple[str, ...] = ("referral", "walk_in", "web_form", "phone", "social_ad")
CHANNEL_BASELINE = "web_form"
BUDGET_BANDS: tuple[str, ...] = ("under_20k", "20k_35k", "35k_55k", "55k_plus")
MODEL_SEGMENTS: tuple[str, ...] = ("economy", "sedan", "suv_truck", "commercial", "luxury")
SEGMENT_BASELINE = "luxury"
NEUTRAL_RFM_SCORE = 3.0  # midpoint quintile, used for "New" customers with no RFM history
MIN_RESOLVED_LEADS_TO_TRAIN = 20  # below this, there's no meaningful temporal split to fit on

FEATURE_LABELS: dict[str, str] = {
    "budget_level": "Budget band",
    "days_since_creation": "Time since lead was created",
    "interaction_count": "Number of interactions",
    "customer_rfm_score": "Customer purchase history",
    "season_sin": "Seasonality",
    "season_cos": "Seasonality",
    **{f"channel__{c}": f"Source: {c.replace('_', ' ').title()}" for c in CHANNELS},
    **{f"segment__{s}": f"Interested in: {s.replace('_', ' ').title()}" for s in MODEL_SEGMENTS},
}

PSI_MONITORED_FEATURES: tuple[str, ...] = (
    *(f"channel__{c}" for c in CHANNELS if c != CHANNEL_BASELINE),
    "budget_level",
    *(f"segment__{s}" for s in MODEL_SEGMENTS if s != SEGMENT_BASELINE),
    "customer_rfm_score",
)
"""FR-074's drift check compares this run's training population (resolved leads, spanning the
full history) against its scoring population (currently-open leads, which are inherently recent
by definition) -- so `days_since_creation`, `season_sin`/`season_cos`, and `interaction_count`
are *mechanically* different between the two populations regardless of any genuine change in the
incoming lead mix (an open lead can't have accumulated as many days or interactions as an
already-resolved one). Monitoring those would make the drift alert fire on every single run,
which is not a useful signal. Only the compositional features here -- what channels, budget
tiers, vehicle segments, and customer quality leads are coming from -- are meaningfully
exchangeable between the two populations, so drift in *those* is the actionable signal."""


@dataclasses.dataclass(frozen=True)
class LeadFeatureRow:
    lead_id: str
    channel: str
    budget_band: str
    model_segment: str
    created_at: datetime
    interaction_count: int
    customer_rfm_score: float | None
    won: bool | None  # None for still-open leads; required (True/False) for training rows


@dataclasses.dataclass(frozen=True)
class FeatureContribution:
    label: str
    contribution: float


@dataclasses.dataclass(frozen=True)
class ScoredLead:
    lead_id: str
    conversion_probability: float
    top_features: list[FeatureContribution]


@dataclasses.dataclass(frozen=True)
class TrainingMetrics:
    roc_auc: float
    pr_auc: float
    brier_score: float
    n_train: int
    n_validate: int


@dataclasses.dataclass(frozen=True)
class LeadScoringResult:
    scored: list[ScoredLead]
    metrics: TrainingMetrics
    train_features: pd.DataFrame
    score_features: pd.DataFrame
    explain_coefficients: dict[str, float]
    """The interpretable `explain_model`'s fitted coefficients, by feature name — exposed for
    QA-003(c)'s sign-recovery validation (`test_qa003c_lead_model_sign_recovery.py`) and any
    future model-diagnostics surface; not itself the calibrated probability."""


def build_feature_matrix(rows: list[LeadFeatureRow], *, as_of: datetime) -> pd.DataFrame:
    """One row per lead, deterministic column order. Unseen/unrecognized categorical values
    (e.g. a `budget_band` string not in `BUDGET_BANDS`) fall back to the baseline level rather
    than raising, per spec.md's Edge Cases — a lead with unusual data still gets scored."""
    records = []
    for r in rows:
        rec: dict[str, float] = {"lead_id": r.lead_id}  # type: ignore[dict-item]
        for c in CHANNELS:
            if c != CHANNEL_BASELINE:
                rec[f"channel__{c}"] = 1.0 if r.channel == c else 0.0
        budget_level = BUDGET_BANDS.index(r.budget_band) if r.budget_band in BUDGET_BANDS else 0
        rec["budget_level"] = float(budget_level)
        for s in MODEL_SEGMENTS:
            if s != SEGMENT_BASELINE:
                rec[f"segment__{s}"] = 1.0 if r.model_segment == s else 0.0
        as_of_utc = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=UTC)
        created_utc = (
            r.created_at if r.created_at.tzinfo is not None else r.created_at.replace(tzinfo=UTC)
        )
        days = (as_of_utc - created_utc).total_seconds() / 86400.0
        rec["days_since_creation"] = max(days, 0.0)
        rec["interaction_count"] = float(r.interaction_count)
        rec["customer_rfm_score"] = (
            float(r.customer_rfm_score) if r.customer_rfm_score is not None else NEUTRAL_RFM_SCORE
        )
        month = created_utc.month
        rec["season_sin"] = float(np.sin(2 * np.pi * month / 12))
        rec["season_cos"] = float(np.cos(2 * np.pi * month / 12))
        records.append(rec)
    df = pd.DataFrame(records).set_index("lead_id")
    feature_cols = sorted(c for c in df.columns if c != "lead_id")
    return df[feature_cols]


def temporal_split(
    rows: list[LeadFeatureRow], *, train_fraction: float = 0.8
) -> tuple[list[LeadFeatureRow], list[LeadFeatureRow]]:
    """DS-CUST-005: leads ordered by `created_at`, earliest `train_fraction` train, remainder
    validate — never shuffled, so a lead created after the split point can never leak into the
    training fold via random chance."""
    resolved = sorted((r for r in rows if r.won is not None), key=lambda r: r.created_at)
    split_idx = int(len(resolved) * train_fraction)
    return resolved[:split_idx], resolved[split_idx:]


def _top_contributions(
    coef: np.ndarray, standardized_row: np.ndarray, feature_names: list[str], *, k: int = 3
) -> list[FeatureContribution]:
    contributions = coef * standardized_row
    order = np.argsort(-np.abs(contributions))[:k]
    return [
        FeatureContribution(
            label=FEATURE_LABELS.get(feature_names[i], feature_names[i]),
            contribution=float(contributions[i]),
        )
        for i in order
    ]


def train_and_score(
    resolved_rows: list[LeadFeatureRow],
    open_rows: list[LeadFeatureRow],
    *,
    as_of: datetime,
    train_fraction: float = 0.8,
) -> LeadScoringResult:
    """Raises `ValueError` if there aren't enough resolved leads to fit a temporal split at all
    (spec.md's Edge Cases: a brand-new environment should fail the run with a clear reason, not
    produce a meaningless model)."""
    if len(resolved_rows) < MIN_RESOLVED_LEADS_TO_TRAIN:
        raise ValueError(
            f"Only {len(resolved_rows)} resolved leads available; need at least "
            f"{MIN_RESOLVED_LEADS_TO_TRAIN} to fit a temporal train/validation split."
        )

    train_rows, val_rows = temporal_split(resolved_rows, train_fraction=train_fraction)
    if len({r.won for r in train_rows}) < 2 or len({r.won for r in val_rows}) < 2:
        raise ValueError(
            "Training or validation split has only one class present (all won or all lost) — "
            "cannot fit or evaluate a binary classifier."
        )

    train_df = build_feature_matrix(train_rows, as_of=as_of)
    val_df = build_feature_matrix(val_rows, as_of=as_of)
    score_df = build_feature_matrix(open_rows, as_of=as_of) if open_rows else train_df.iloc[0:0]

    feature_names = list(train_df.columns)
    y_train = np.array([1 if r.won else 0 for r in train_rows])
    y_val = np.array([1 if r.won else 0 for r in val_rows])

    scaler = StandardScaler()
    x_train = scaler.fit_transform(train_df.to_numpy())
    x_val = scaler.transform(val_df.to_numpy())
    x_score = (
        scaler.transform(score_df.to_numpy())
        if len(score_df)
        else np.empty((0, len(feature_names)))
    )

    # `penalty` left at its default ("l2", DS-CUST-003's requirement) rather than passed
    # explicitly -- sklearn 1.8+ deprecates the `penalty="l2"` spelling in favor of just using
    # the default, ahead of its removal in 1.10.
    explain_model = LogisticRegression(class_weight="balanced", max_iter=1000)
    explain_model.fit(x_train, y_train)

    calibrated_model = CalibratedClassifierCV(
        LogisticRegression(class_weight="balanced", max_iter=1000),
        method="isotonic",
        cv=5,
    )
    calibrated_model.fit(x_train, y_train)

    val_probs = calibrated_model.predict_proba(x_val)[:, 1]
    metrics = TrainingMetrics(
        roc_auc=float(roc_auc_score(y_val, val_probs)),
        pr_auc=float(average_precision_score(y_val, val_probs)),
        brier_score=float(brier_score_loss(y_val, val_probs)),
        n_train=len(train_rows),
        n_validate=len(val_rows),
    )

    scored: list[ScoredLead] = []
    if len(score_df):
        score_probs = calibrated_model.predict_proba(x_score)[:, 1]
        coef = explain_model.coef_[0]
        for idx, lead_id in enumerate(score_df.index):
            scored.append(
                ScoredLead(
                    lead_id=str(lead_id),
                    conversion_probability=float(score_probs[idx]),
                    top_features=_top_contributions(coef, x_score[idx], feature_names),
                )
            )

    explain_coefficients = dict(zip(feature_names, explain_model.coef_[0], strict=True))

    return LeadScoringResult(
        scored=scored,
        metrics=metrics,
        train_features=train_df,
        score_features=score_df,
        explain_coefficients=explain_coefficients,
    )
