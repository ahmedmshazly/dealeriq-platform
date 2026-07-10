# packages/analytics — DealerIQ Analytics

Python library for forecasting, inventory intelligence, anomaly detection, and customer/lead
analytics (`docs/srs/DealerIQ-SRS.md` §6). Imported by `apps/api`'s job runner; also runnable
standalone as a CLI for experiments and the benchmark harness (Phase 10,
`python -m dealeriq_analytics.benchmark --config ...`).

Empty at Phase 0 by design — this package exists now so the workspace/packaging/test pattern
is established before any domain logic lands, starting with the synthetic data generator
(Phase 3) and the forecasting engine (Phase 4).

## Design discipline (constitution Principle VII, QA-002)

Every metric (MASE, pinball loss, empirical coverage, SBC classification, Croston/SBA/TSB
outputs) is unit-tested against hand-computed fixtures or published toy examples **before**
being wired into any pipeline. Seasonal Naive is the mandatory champion floor (DS-FC-006) — this
is enforced in code, not just documented.

## Tests

```bash
uv run pytest packages/analytics/tests --cov=dealeriq_analytics --cov-report=term-missing
```
