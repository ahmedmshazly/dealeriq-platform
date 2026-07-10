# ADR-017: `lifelines` for Kaplan-Meier; hand-implemented, unit-tested GESD

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: DS-INV-004, DS-ANO-002, QA-002

## Context

DS-INV-004 needs a Kaplan-Meier survival curve of time-to-sale per segment. DS-ANO-002 needs the
generalized Extreme Studentized Deviate (ESD) test to confirm STL/MAD-flagged anomalies. No
actively maintained Python package implements standalone GESD (it exists inside some outlier
-detection suites but not as a small, auditable primitive).

## Decision

Use `lifelines` for Kaplan-Meier estimation. Hand-implement the generalized ESD test in
`packages/analytics`, unit-tested directly against Rosner (1983)'s published worked example
(same numeric inputs, same expected number of detected outliers).

## Consequences

- `lifelines` is the de facto maintained survival-analysis package for Python; no reason to
  hand-roll Kaplan-Meier.
- GESD is small enough (a repeated max-deviation test with a decreasing critical-value table) to
  implement and test like any other metric under QA-002's "validate against hand-computed/
  published fixtures before wiring into a pipeline" discipline — this is a deliberate,
  documented implementation, not a fabricated shortcut.
