# ADR-022: RFM segment-name mapping

- Status: Accepted
- Date: 2026-07-11
- Requirement refs: DS-CUST-001, FR-033

## Context

DS-CUST-001 requires customers to be scored on Recency/Frequency/Monetary quintiles and mapped to
named segments, giving illustrative examples ("Champions, At-Risk, Hibernating") but not an exact
segment table. Standard RFM practice (Putler/HubSpot-style 11-segment tables) exists, but a
smaller table is sufficient for v1.0's UI and is easier for a Manager to act on at a glance.

## Decision

Five named segments, computed from per-customer R/F/M quintile scores (1-5 each, 5 = best):

- **Champions**: `R >= 4 AND F >= 4 AND M >= 4` — recent, frequent, high-value.
- **Loyal Customers**: `F >= 4` and not already Champions — frequent buyers regardless of
  recency/value.
- **At Risk**: `R <= 2 AND (F >= 3 OR M >= 3)` — used to buy often or spend a lot, but it's been a
  while.
- **New**: zero completed orders — RFM is undefined without at least one transaction; this is a
  distinct, explicit segment, never a fabricated quintile score (spec.md's Edge Cases).
- **Hibernating**: everyone else — low across the board.

Rules are evaluated in the order listed (first match wins), so a customer can't satisfy two
segments' conditions simultaneously in an ambiguous way.

## Consequences

- A defensible, documented simplification of standard RFM segmentation practice, not an invented
  one — the rule shapes (recent+frequent+valuable → Champions; not-recent-but-was-valuable →
  At Risk; everything else → Hibernating) mirror the same logic larger segment tables use, just
  collapsed to five names instead of eleven.
- Quintile boundaries themselves are the standard `pandas.qcut`-style 20/40/60/80th-percentile
  cutoffs computed across the customer population per run (5 is the best quintile for R
  meaning "most recent," and for F/M meaning "highest"), consistent with how Phase 5's ABC/XYZ
  classification was already cutoff-driven and disclosed as such.
- Adding an 11-segment table later (if ever needed) is additive — it doesn't require revisiting
  the underlying quintile computation, only the segment-name mapping function.
