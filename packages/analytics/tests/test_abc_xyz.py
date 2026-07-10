import pandas as pd

from dealeriq_analytics.inventory.abc_xyz import classify_abc_xyz, demand_cv


def test_demand_cv_hand_computed() -> None:
    # [2, 4, 6, 8] -> mean=5, population std=sqrt(((3)^2+(1)^2+(1)^2+(3)^2)/4)=sqrt(20/4)=sqrt(5)
    series = pd.Series([2.0, 4.0, 6.0, 8.0])
    cv = demand_cv(series)
    assert abs(cv - (5**0.5) / 5) < 1e-9


def test_demand_cv_zero_mean_is_infinite() -> None:
    assert demand_cv(pd.Series([0.0, 0.0, 0.0])) == float("inf")


def test_abc_classification_hand_computed_boundaries() -> None:
    # Revenue: A=800, B=150, C=50 -> total=1000
    # cumulative after A: 0.80 -> exactly at the 80% cutoff, inclusive boundary -> A
    # cumulative after B: 0.95 -> exactly at the 95% cutoff, inclusive boundary -> B
    # cumulative after C: 1.00 -> C
    revenue = {"model_a": 800.0, "model_b": 150.0, "model_c": 50.0}
    demand = {
        "model_a": pd.Series([10.0, 10.0, 10.0]),  # cv=0 -> X
        "model_b": pd.Series([10.0, 10.0, 10.0]),
        "model_c": pd.Series([10.0, 10.0, 10.0]),
    }
    result = classify_abc_xyz(revenue, demand)

    assert result["model_a"].abc == "A"
    assert abs(result["model_a"].cumulative_share - 0.80) < 1e-9
    assert result["model_b"].abc == "B"
    assert abs(result["model_b"].cumulative_share - 0.95) < 1e-9
    assert result["model_c"].abc == "C"
    assert abs(result["model_c"].cumulative_share - 1.0) < 1e-9


def test_xyz_classification_hand_computed_boundaries() -> None:
    revenue = {"low_var": 100.0, "mid_var": 100.0, "high_var": 100.0}
    demand = {
        # cv=0 (constant) -> X
        "low_var": pd.Series([5.0, 5.0, 5.0, 5.0]),
        # mean=5, std=2 -> cv=0.4 -> X (< 0.5)
        "mid_var": pd.Series([3.0, 7.0, 3.0, 7.0]),
        # mean=5, std=5 -> cv=1.0 -> Z (>= 1.0, not < 1.0)
        "high_var": pd.Series([0.0, 10.0, 0.0, 10.0]),
    }
    result = classify_abc_xyz(revenue, demand)

    assert result["low_var"].xyz == "X"
    assert abs(result["mid_var"].demand_cv - 0.4) < 1e-9
    assert result["mid_var"].xyz == "X"
    assert abs(result["high_var"].demand_cv - 1.0) < 1e-9
    assert result["high_var"].xyz == "Z"


def test_a_single_model_with_all_revenue_is_a_and_gets_its_own_cv() -> None:
    revenue = {"only_model": 500.0}
    demand = {"only_model": pd.Series([1.0, 2.0, 3.0])}
    result = classify_abc_xyz(revenue, demand)
    assert result["only_model"].abc == "A"
    assert result["only_model"].cumulative_share == 1.0
