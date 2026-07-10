"""DS-FC-003's method pool, via statsforecast (ADR-005, narrowed by ADR-018 to be the sole
implementation — statsmodels stays scoped to STL for Phase 5's anomaly detector).

`SimpleExponentialSmoothingOptimized` (auto-tuned alpha) is used for "Simple Exponential
Smoothing" rather than the fixed-alpha `SimpleExponentialSmoothing`, so the pipeline never has to
justify a hand-picked smoothing constant — distinct from "ETS (automatic)", which searches over
error/trend/seasonal *component* combinations, not just one exponential-smoothing recursion's
alpha.

TSB needs `alpha_d`/`alpha_p` (demand/probability smoothing constants) with no auto-tuned
variant available in statsforecast; 0.1/0.1 are used as reasonable, commonly-cited defaults for
intermittent-demand smoothing (Teunter, Syntetos & Babai 2011's own worked examples use this
range) — a documented default, not a tuned hyperparameter.

AutoARIMA's seasonal search space is narrowed (`max_P=1, max_Q=1, nmodels=20`, down from the
defaults of 2/2/94) — empirically measured: with `season_length=52` (weekly/annual) and
DS-FC-004's expanding-window CV refitting AutoARIMA at every one of 24 folds per series, the
default search space made a single 81-series run take 20+ minutes even parallelized across 8
cores. Weekly-with-annual-seasonality is a well-known expensive case for stepwise ARIMA search
(the large seasonal lag inflates the seasonal-difference/seasonal-AR/MA candidate space); this
is a genuine, documented tradeoff of search breadth for tractable on-demand runtime, not a
silent quality cut — AutoARIMA is still a real automatic search, just over a narrower space.
"""

from typing import Any

from statsforecast.models import (
    TSB,
    AutoARIMA,
    AutoETS,
    CrostonClassic,
    CrostonSBA,
    Naive,
    SeasonalNaive,
    SimpleExponentialSmoothingOptimized,
)

SEASONAL_NAIVE_ALIAS = "SeasonalNaive"
TSB_ALPHA_D = 0.1
TSB_ALPHA_P = 0.1


def build_method_pool(season_length: int) -> list[Any]:
    """One instance per DS-FC-003 method. `season_length` is 52 for the weekly-annual cycle
    Phase 3's demand generator actually used."""
    return [
        Naive(),
        SeasonalNaive(season_length=season_length, alias=SEASONAL_NAIVE_ALIAS),
        SimpleExponentialSmoothingOptimized(),
        AutoETS(season_length=season_length),
        AutoARIMA(season_length=season_length, max_P=1, max_Q=1, nmodels=20),
        CrostonClassic(),
        CrostonSBA(),
        TSB(alpha_d=TSB_ALPHA_D, alpha_p=TSB_ALPHA_P),
    ]
