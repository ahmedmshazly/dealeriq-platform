from dealeriq_analytics.customer.rfm import (
    SEGMENT_AT_RISK,
    SEGMENT_CHAMPIONS,
    SEGMENT_HIBERNATING,
    SEGMENT_LOYAL,
    SEGMENT_NEW,
    CustomerOrderStats,
    compute_rfm,
)


def _stats(
    customer_id: str, recency_days: float, frequency: int, monetary: float
) -> CustomerOrderStats:
    return CustomerOrderStats(
        customer_id=customer_id, recency_days=recency_days, frequency=frequency, monetary=monetary
    )


def test_zero_order_customer_gets_new_segment_not_a_fabricated_quintile() -> None:
    stats = {
        "never_bought": _stats("never_bought", recency_days=9999.0, frequency=0, monetary=0.0),
        "buyer": _stats("buyer", recency_days=5.0, frequency=3, monetary=30000.0),
    }
    result = compute_rfm(stats)
    assert result["never_bought"].segment == SEGMENT_NEW
    assert result["never_bought"].recency_score is None
    assert result["never_bought"].frequency_score is None
    assert result["never_bought"].monetary_score is None


def test_all_zero_order_customers_all_get_new() -> None:
    stats = {
        f"c{i}": _stats(f"c{i}", recency_days=9999.0, frequency=0, monetary=0.0) for i in range(5)
    }
    result = compute_rfm(stats)
    assert all(r.segment == SEGMENT_NEW for r in result.values())


def test_champions_are_recent_frequent_and_high_value() -> None:
    # A population of 10 where "best" sits at the very top of every dimension -> its quintile
    # scores are all 5, and ADR-022's Champions rule (R>=4, F>=4, M>=4) fires.
    stats = {}
    for i in range(10):
        stats[f"c{i}"] = _stats(
            f"c{i}",
            recency_days=float(i + 1),  # c0 has recency_days=1 (most recent, best)
            frequency=10 - i,  # c0 has frequency=10 (most frequent, best)
            monetary=float((10 - i) * 1000),  # c0 has monetary=10000 (highest, best)
        )
    result = compute_rfm(stats)
    assert result["c0"].segment == SEGMENT_CHAMPIONS
    assert result["c0"].recency_score == 5
    assert result["c0"].frequency_score == 5
    assert result["c0"].monetary_score == 5


def test_hibernating_is_worst_across_the_board() -> None:
    stats = {}
    for i in range(10):
        stats[f"c{i}"] = _stats(
            f"c{i}", recency_days=float(i + 1), frequency=10 - i, monetary=float((10 - i) * 1000)
        )
    result = compute_rfm(stats)
    # c9: largest recency_days (least recent), smallest frequency/monetary -> worst on all three
    assert result["c9"].segment == SEGMENT_HIBERNATING
    assert result["c9"].recency_score == 1
    assert result["c9"].frequency_score == 1
    assert result["c9"].monetary_score == 1


def test_at_risk_was_valuable_but_has_gone_quiet() -> None:
    # c0 is the population's worst on recency (least recent) but its best on frequency/monetary
    # -> At Risk (R<=2 and (F>=3 or M>=3)), not Champions (fails the R>=4 test).
    stats = {"c0": _stats("c0", recency_days=1000.0, frequency=10, monetary=10000.0)}
    for i in range(1, 10):
        stats[f"c{i}"] = _stats(
            f"c{i}", recency_days=float(100 * i), frequency=10 - i, monetary=float((10 - i) * 1000)
        )
    result = compute_rfm(stats)
    assert result["c0"].recency_score == 1
    assert result["c0"].frequency_score == 5
    assert result["c0"].monetary_score == 5
    assert result["c0"].segment == SEGMENT_AT_RISK


def test_loyal_is_frequent_with_moderate_recency() -> None:
    # c9 is the population's most frequent buyer (F score=5) but sits in the middle of the
    # recency distribution (R score=3, neither <=2 nor >=4) -> excluded from both Champions
    # (needs R>=4) and At Risk (needs R<=2), landing cleanly in Loyal (F>=4).
    stats = {
        "c0": _stats("c0", recency_days=10.0, frequency=1, monetary=100.0),
        "c1": _stats("c1", recency_days=20.0, frequency=2, monetary=200.0),
        "c2": _stats("c2", recency_days=30.0, frequency=3, monetary=300.0),
        "c3": _stats("c3", recency_days=40.0, frequency=4, monetary=400.0),
        "c4": _stats("c4", recency_days=60.0, frequency=5, monetary=500.0),
        "c5": _stats("c5", recency_days=70.0, frequency=6, monetary=600.0),
        "c6": _stats("c6", recency_days=80.0, frequency=7, monetary=700.0),
        "c7": _stats("c7", recency_days=90.0, frequency=8, monetary=800.0),
        "c8": _stats("c8", recency_days=100.0, frequency=9, monetary=900.0),
        "c9": _stats("c9", recency_days=55.0, frequency=100, monetary=50.0),
    }
    result = compute_rfm(stats)
    assert result["c9"].recency_score == 3
    assert result["c9"].frequency_score == 5
    assert result["c9"].segment == SEGMENT_LOYAL
