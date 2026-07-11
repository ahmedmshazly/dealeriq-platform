from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from dealeriq_analytics.customer.lead_scoring import (
    BUDGET_BANDS,
    CHANNEL_BASELINE,
    CHANNELS,
    MIN_RESOLVED_LEADS_TO_TRAIN,
    LeadFeatureRow,
    build_feature_matrix,
    temporal_split,
    train_and_score,
)

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)


def _lead(
    lead_id: str,
    *,
    created_at: datetime,
    won: bool | None,
    channel: str = CHANNEL_BASELINE,
    budget_band: str = BUDGET_BANDS[0],
    model_segment: str = "sedan",
    interaction_count: int = 1,
    customer_rfm_score: float | None = 3.0,
) -> LeadFeatureRow:
    return LeadFeatureRow(
        lead_id=lead_id,
        channel=channel,
        budget_band=budget_band,
        model_segment=model_segment,
        created_at=created_at,
        interaction_count=interaction_count,
        customer_rfm_score=customer_rfm_score,
        won=won,
    )


def test_build_feature_matrix_unseen_categorical_falls_back_to_baseline() -> None:
    row = _lead(
        "l1",
        created_at=AS_OF - timedelta(days=10),
        won=None,
        channel="carrier_pigeon",
        budget_band="not_a_band",
    )
    df = build_feature_matrix([row], as_of=AS_OF)
    # Baseline channel/segment mean every one-hot column is 0; unrecognized budget_band falls
    # back to the lowest ordinal level (0), not an error.
    for c in CHANNELS:
        if c != CHANNEL_BASELINE:
            assert df.loc["l1", f"channel__{c}"] == 0.0
    assert df.loc["l1", "budget_level"] == 0.0


def test_build_feature_matrix_days_since_creation_never_negative() -> None:
    row = _lead("l1", created_at=AS_OF + timedelta(days=5), won=None)  # created "in the future"
    df = build_feature_matrix([row], as_of=AS_OF)
    assert df.loc["l1", "days_since_creation"] == 0.0


def test_temporal_split_never_leaks_a_future_lead_into_training() -> None:
    rows = [
        _lead(f"l{i}", created_at=AS_OF - timedelta(days=100 - i), won=(i % 2 == 0))
        for i in range(100)
    ]
    train, val = temporal_split(rows, train_fraction=0.8)
    assert len(train) == 80
    assert len(val) == 20
    assert max(r.created_at for r in train) <= min(r.created_at for r in val)


def test_temporal_split_ignores_unresolved_leads() -> None:
    rows = [_lead("open1", created_at=AS_OF, won=None)] + [
        _lead(f"l{i}", created_at=AS_OF - timedelta(days=100 - i), won=True) for i in range(30)
    ]
    train, val = temporal_split(rows, train_fraction=0.8)
    assert all(r.won is not None for r in train + val)
    assert len(train) + len(val) == 30


def test_train_and_score_raises_below_minimum_resolved_leads() -> None:
    rows = [_lead(f"l{i}", created_at=AS_OF - timedelta(days=i), won=True) for i in range(5)]
    with pytest.raises(ValueError, match="Only 5 resolved leads"):
        train_and_score(rows, [], as_of=AS_OF)


def test_train_and_score_recovers_a_strong_known_signal() -> None:
    # A population where channel="referral" always wins and channel="social_ad" always loses,
    # everything else held constant -- the fitted model should recover this near-deterministic
    # signal with high discrimination (this is a sign-recovery-style check against a known,
    # hand-constructed ground truth, not real seeded data -- QA-003(b)'s real-data validation
    # equivalent lives in the integration test against the actual database).
    rng = np.random.default_rng(0)
    rows = []
    n = 200
    for i in range(n):
        created_at = AS_OF - timedelta(days=400 - i * 2)
        won = bool(rng.random() < (0.95 if i % 2 == 0 else 0.05))
        channel = "referral" if i % 2 == 0 else "social_ad"
        rows.append(_lead(f"l{i}", created_at=created_at, won=won, channel=channel))

    result = train_and_score(rows, [], as_of=AS_OF, train_fraction=0.8)
    assert result.metrics.roc_auc > 0.8
    assert result.metrics.n_train == int(n * 0.8)
    assert result.metrics.n_validate == n - int(n * 0.8)


def test_train_and_score_produces_top3_explanations_for_open_leads() -> None:
    rng = np.random.default_rng(1)
    n = 200
    resolved = []
    for i in range(n):
        created_at = AS_OF - timedelta(days=400 - i * 2)
        won = bool(rng.random() < (0.9 if i % 2 == 0 else 0.1))
        channel = "referral" if i % 2 == 0 else "social_ad"
        resolved.append(_lead(f"l{i}", created_at=created_at, won=won, channel=channel))
    open_leads = [
        _lead("open1", created_at=AS_OF - timedelta(days=5), won=None, channel="referral")
    ]

    result = train_and_score(resolved, open_leads, as_of=AS_OF)
    assert len(result.scored) == 1
    scored = result.scored[0]
    assert scored.lead_id == "open1"
    assert 0.0 <= scored.conversion_probability <= 1.0
    assert len(scored.top_features) == 3
    assert all(isinstance(f.label, str) and f.label for f in scored.top_features)


def test_train_and_score_raises_on_single_class_split() -> None:
    rows = [_lead(f"l{i}", created_at=AS_OF - timedelta(days=100 - i), won=True) for i in range(30)]
    with pytest.raises(ValueError, match="only one class"):
        train_and_score(rows, [], as_of=AS_OF)


def test_min_resolved_leads_constant_is_reasonable() -> None:
    # Documents the threshold itself so a future change to it is a deliberate, visible diff.
    assert MIN_RESOLVED_LEADS_TO_TRAIN == 20
