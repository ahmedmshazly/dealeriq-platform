# DealerIQ Backlog

P1/P2 requirements deliberately deferred beyond a phase's stated SRS §13 ID range, per the
constitution's scope-discipline rule. Each entry names the requirement, why it was deferred, and
which phase would naturally pick it up if prioritized later.

| Requirement | Priority | Deferred from phase | Rationale |
|---|---|---|---|
| FR-007 (TOTP 2FA for Admins) | P2 | 1 | Real added complexity (secret provisioning, QR, recovery codes) for low value at this stage. |
| FR-082 (admin settings console) | P1 | 1 (unassigned in SRS §13) | SRS never assigns this to a phase. FR-081 (audit browse) was folded into Phase 1 since the exit demo needs it; FR-082 has no such forcing dependency. Natural home is alongside Phase 6 (alert rule params, FR-065) or Phase 9 hardening - revisit then. |
| FR-025 (CSV import dry-run w/ row-level validation) | P1 | 2 | Export ships; import with row-level validation is a genuine scope trap. Revisit alongside admin console work. |
| FR-034 (bulk lead reassignment) | P2 | 2 | Nice-to-have UI convenience, not load-bearing for any downstream phase. |
| GEN-005 (persona-driven discount variation) | P1 | 3 | Addable later as a generator version bump without breaking reproducibility of earlier runs. |
| DS-FC-008 (bottom-up forecast reconciliation diagnostic) | P1 | 4 | Diagnostic-only; doesn't block the champion-selection or alerting pipeline. |
| DS-FC-009 (per-fold CV residual diagnostics view) | P1 | 4 | Fan chart (the P0 output) ships; the deeper diagnostics view is analyst-workbench polish. |
| DS-INV-005 (Cox proportional-hazards pricing model) | P2 | 5 | Kaplan-Meier (P1, in range) ships; Cox is an explicit stretch beyond it. |
| FR-066 (mute a dedup key) | P2 | 6 | Convenience feature on top of the core alert lifecycle. |
| DS-CUST-003 (HistGradientBoosting challenger + champion/challenger promotion) | P1 | 7 | SRS says the challenger "MAY be promoted" - explicitly optional. The calibrated LR baseline satisfies every P0 item in this phase's scope; revisit once real production lead volume makes a GBM's extra capacity worth the added explainability cost (permutation importance vs. LR's plain coefficients). |
| FR-051 (per-salesperson quota/target management) | P2 | 8 | A full quota system (per-person targets, ramping new hires, seasonal adjustment) is unscoped expansion beyond "my sales vs. target" existing at all. This phase uses a single admin-configurable default target applied uniformly (ADR-024); revisit alongside FR-082's admin settings console. |
| NFR-005 (analytics job retry-once-with-backoff) | P0 | 9 (found while writing the ops runbook - not implemented) | Verified directly against the code (`routes/jobs.py`'s `trigger_job_route`, `core/scheduler.py`'s cron callbacks): a failing job transitions to `FAILED` and stops there - no automatic retry exists anywhere. The other half of NFR-005 ("last successful run stays served") *is* real and correct today - every serving route filters to `status=SUCCEEDED`. Retry-with-backoff needs its own design (where retry state lives, how it interacts with the FR-072 concurrency guard, whether a retry is a new `AnalyticsRun` row or an update to the failed one) - out of scope for a docs-and-tooling hardening phase. The new runbook documents the real current behavior (manual re-trigger or wait for the next cron) rather than the aspirational one. |
| QA-003 extension: assert which methods were actually evaluated, not just properties of whichever champion was selected | P1 | 10 (found alongside ADR-025's conformal-intervals bug fix) | ADR-025 documents a real bug where 4 of 8 DS-FC-003 methods silently failed CV on every run since Phase 4, undetected because QA-003(a) only checks the *selected* champion's properties, not the composition of the pool it was selected from. A pool-completeness assertion (e.g. "every configured method produced at least one valid CV result across a representative series set") would have caught this immediately. A genuinely separate, additive testing improvement - not built as part of the bug-fix itself. |

Add new rows here as later phases surface additional deferrals - do not build these
opportunistically inside an unrelated phase.
