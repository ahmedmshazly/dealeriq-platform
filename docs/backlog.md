# DealerIQ Backlog

P1/P2 requirements deliberately deferred beyond a phase's stated SRS §13 ID range, per the
constitution's scope-discipline rule. Each entry names the requirement, why it was deferred, and
which phase would naturally pick it up if prioritized later.

| Requirement | Priority | Deferred from phase | Rationale |
|---|---|---|---|
| FR-007 (TOTP 2FA for Admins) | P2 | 1 | Real added complexity (secret provisioning, QR, recovery codes) for low value at this stage. |
| FR-025 (CSV import dry-run w/ row-level validation) | P1 | 2 | Export ships; import with row-level validation is a genuine scope trap. Revisit alongside admin console work. |
| FR-034 (bulk lead reassignment) | P2 | 2 | Nice-to-have UI convenience, not load-bearing for any downstream phase. |
| GEN-005 (persona-driven discount variation) | P1 | 3 | Addable later as a generator version bump without breaking reproducibility of earlier runs. |
| DS-FC-008 (bottom-up forecast reconciliation diagnostic) | P1 | 4 | Diagnostic-only; doesn't block the champion-selection or alerting pipeline. |
| DS-FC-009 (per-fold CV residual diagnostics view) | P1 | 4 | Fan chart (the P0 output) ships; the deeper diagnostics view is analyst-workbench polish. |
| DS-INV-005 (Cox proportional-hazards pricing model) | P2 | 5 | Kaplan-Meier (P1, in range) ships; Cox is an explicit stretch beyond it. |
| FR-066 (mute a dedup key) | P2 | 6 | Convenience feature on top of the core alert lifecycle. |

Add new rows here as later phases surface additional deferrals — do not build these
opportunistically inside an unrelated phase.
