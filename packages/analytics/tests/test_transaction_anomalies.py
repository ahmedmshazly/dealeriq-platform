from dealeriq_analytics.anomalies_detector.transaction_anomalies import (
    MIN_ORDERS_FOR_DISCOUNT_STATS,
    OrderRecord,
    detect_transaction_anomalies,
)


def test_hand_computed_discount_fraction_threshold() -> None:
    # list_price=100 for all. Fractions: [0.05, 0.05, 0.05, 0.05, 0.30]
    # mean = (0.05*4 + 0.30)/5 = 0.5/5 = 0.10
    # population std: deviations [-0.05,-0.05,-0.05,-0.05,0.20], sq=[0.0025]*4+[0.04]
    #   sum=0.05, /5=0.01, std=0.1
    # threshold_fraction (k=3) = 0.10 + 3*0.1 = 0.40 -> none should exceed 0.40, so 0 anomalies
    orders = [
        OrderRecord("o1", "m1", 100.0, 95.0),
        OrderRecord("o2", "m1", 100.0, 95.0),
        OrderRecord("o3", "m1", 100.0, 95.0),
        OrderRecord("o4", "m1", 100.0, 95.0),
        OrderRecord("o5", "m1", 100.0, 70.0),
    ]
    anomalies = detect_transaction_anomalies(orders, k=3.0)
    assert anomalies == []


def test_a_clear_outlier_below_threshold_is_flagged() -> None:
    # 19 orders at fraction 0.0 (no discount) + 1 outlier at fraction 0.5, list_price=100.
    # mean = 0.5/20 = 0.025
    # population variance = (19*(0-0.025)^2 + (0.5-0.025)^2) / 20
    #                      = (19*0.000625 + 0.225625) / 20 = (0.011875+0.225625)/20 = 0.01187500
    # std = sqrt(0.011875) = 0.108972...
    # threshold_fraction = 0.025 + 3*0.108972 = 0.351917 -> outlier's 0.5 exceeds it
    orders = [OrderRecord(f"o{i}", "m1", 100.0, 100.0) for i in range(19)]
    orders.append(OrderRecord("outlier", "m1", 100.0, 50.0))
    anomalies = detect_transaction_anomalies(orders, k=3.0)
    assert len(anomalies) == 1
    assert anomalies[0].order_id == "outlier"
    assert abs(anomalies[0].discount_fraction_mean - 0.025) < 1e-9
    assert abs(anomalies[0].discount_fraction_std - 0.108972) < 1e-5


def test_model_with_fewer_than_minimum_orders_is_skipped() -> None:
    assert MIN_ORDERS_FOR_DISCOUNT_STATS == 5
    orders = [
        OrderRecord("o1", "m1", 100.0, 95.0),
        OrderRecord("o2", "m1", 100.0, 10.0),  # would be a huge outlier if scored
    ]
    anomalies = detect_transaction_anomalies(orders, k=3.0)
    assert anomalies == []


def test_zero_variance_discount_history_is_skipped_not_divide_by_zero() -> None:
    orders = [OrderRecord(f"o{i}", "m1", 100.0, 90.0) for i in range(6)]
    anomalies = detect_transaction_anomalies(orders, k=3.0)
    assert anomalies == []


def test_different_models_are_scored_independently() -> None:
    m1_orders = [OrderRecord(f"a{i}", "m1", 100.0, 100.0) for i in range(19)]
    m1_orders.append(OrderRecord("a_outlier", "m1", 100.0, 50.0))
    m2_orders = [OrderRecord(f"b{i}", "m2", 200.0, 190.0) for i in range(5)]
    anomalies = detect_transaction_anomalies(m1_orders + m2_orders, k=3.0)
    assert {a.order_id for a in anomalies} == {"a_outlier"}
