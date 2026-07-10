"""QA-003(b) — CI-blocking scientific validation, per the constitution's Phase 4+ mandate (the
same standing QA-003(a) got in Phase 4): the anomaly detector recovers >=80% of injected
anomalies at <=10% false-positive rate.

Runs the real DS-ANO-001/002 detector (STL + robust z-score + generalized ESD) against Phase 3's
real generator output, reconstructed in-memory with the *exact* same RNG spawning sequence
`infra/seed/generate.py`'s `main()` uses (`SeedSequence(config.seed).spawn(7)`, taking only the
first two spawned streams this test needs) — so the injected shocks and near-miss points here are
byte-identical to what's actually in the seeded database's `infra/seed/ground_truth/
anomalies.json`, not just a statistically-similar independent draw. This is the harder, more
novel half of DS-ANO-001..004 (series-level STL/z-score/GESD); DS-ANO-003's transaction-level
discount-outlier detector was verified directly against the real seeded database (15/15 injected
pricing errors recovered, ~1.8% false-positive rate) and is documented in the Phase 5 report
rather than duplicated here as a second slow in-memory pytest.
"""

import numpy as np

from dealeriq_analytics.anomalies_detector.series_anomalies import (
    UnstableSeriesError,
    detect_series_anomalies,
)
from dealeriq_analytics.generator.anomalies import find_near_miss_points, inject_demand_shocks
from dealeriq_analytics.generator.config import GeneratorConfig
from dealeriq_analytics.generator.demand import generate_demand

MIN_RECOVERY_RATE = 0.80
MAX_FALSE_POSITIVE_RATE = 0.10
N_SHOCKS = 20
N_NEAR_MISS = 5


def test_series_anomaly_detector_recovers_injected_shocks_within_fpr_budget() -> None:
    config = GeneratorConfig()
    demand = generate_demand(config)

    # Mirrors infra/seed/generate.py's main() exactly: same SeedSequence spawning order, so
    # rng_anomaly/rng_near_miss here produce the identical injected ground truth the real
    # seeded database has.
    master_seq = np.random.SeedSequence(config.seed)
    rng_anomaly, rng_near_miss, *_ = (np.random.default_rng(s) for s in master_seq.spawn(7))

    mutated_series, shock_records = inject_demand_shocks(demand, rng_anomaly, n_shocks=N_SHOCKS)
    near_miss_records = find_near_miss_points(demand, rng_near_miss, n_near_miss=N_NEAR_MISS)

    injected_positions = {(r.series_key, r.week_index) for r in shock_records}
    near_miss_positions = {(r.series_key, r.week_index) for r in near_miss_records}
    assert len(injected_positions) == N_SHOCKS

    flagged_positions: set[tuple[str, int]] = set()
    total_scoreable_points = 0
    for key, series in mutated_series.items():
        series_key = f"{key[0]}|{key[1]}"
        try:
            anomalies = detect_series_anomalies(series.astype(float))
        except UnstableSeriesError:
            continue
        total_scoreable_points += len(series)
        for anomaly in anomalies:
            flagged_positions.add((series_key, anomaly.week_index))

    recovered = injected_positions & flagged_positions
    recovery_rate = len(recovered) / len(injected_positions)
    assert recovery_rate >= MIN_RECOVERY_RATE, (
        f"Recovered only {len(recovered)}/{len(injected_positions)} "
        f"({recovery_rate:.1%}) injected shocks — QA-003(b) requires >=80%."
    )

    near_miss_flagged = near_miss_positions & flagged_positions
    assert not near_miss_flagged, (
        f"{len(near_miss_flagged)} of the curated near-miss (should-NOT-flag) points were "
        f"flagged: {near_miss_flagged}"
    )

    false_positives = flagged_positions - injected_positions
    clean_points = total_scoreable_points - len(injected_positions)
    false_positive_rate = len(false_positives) / clean_points
    assert false_positive_rate <= MAX_FALSE_POSITIVE_RATE, (
        f"False-positive rate {false_positive_rate:.1%} "
        f"({len(false_positives)}/{clean_points}) exceeds QA-003(b)'s <=10% budget."
    )
