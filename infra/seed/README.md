# infra/seed

Synthetic data generator entrypoints (GEN-001..006, `docs/srs/DealerIQ-SRS.md` §10) land here in
Phase 3. Ground-truth parameters and injected anomaly/lead-coefficient labels used by the
scientific validation tests (QA-003) are exported to `infra/seed/ground_truth/` once the
generator exists.

A lighter-weight `make seed-dev` fixture (a handful of branches/models/units/customers/leads/
orders across every status, no time-series realism) is introduced immediately after Phase 2 for
fast iteration on CRUD/UI work, ahead of the full 156-week statistical generator. Both remain
permanent, separate targets — `seed-dev` for fast local iteration, `seed` (the full generator)
canonical for anything analytics-facing from Phase 3 onward.
