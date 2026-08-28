# packages/analytics — DealerIQ Analytics

Python library for forecasting, inventory intelligence, anomaly detection, and customer/lead
analytics (SRS §6). Imported by `apps/api` job pipelines; also runnable standalone for
experiments and the benchmark harness (`python -m dealeriq_analytics.benchmark`).

## Layout

```
src/dealeriq_analytics/
├── forecasting/          # methods, CV, champion selection, metrics, series helpers
├── inventory/            # ABC-XYZ, reorder, survival
├── anomalies_detector/   # series + transaction anomalies
├── customer/             # RFM, lead scoring, PSI
├── generator/            # synthetic demand / leads / anomalies (seed pipeline)
├── benchmark/            # CLI harness for the research paper
└── sbc.py                # Seasonal behavior classification
tests/                    # unit tests with hand-computed fixtures (QA-002)
```

## Principles

- Metrics are unit-tested against fixtures **before** wiring into API jobs.
- Seasonal Naive is the mandatory forecasting champion floor (DS-FC-006).
- Jobs in the API own persistence and `analytics_runs`; this package stays pure compute.

## Running tests

```bash
uv run pytest packages/analytics/tests
```

## Benchmark / paper

```bash
make benchmark-paper
```

See `docs/explanation/analytics-pipeline.md` and `docs/paper/`.
