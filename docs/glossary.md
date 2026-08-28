---
title: Glossary
description: DealerIQ product and analytics vocabulary (authoritative for the handbook reader).
last-verified: 2026-07-17
---

# Glossary

Study and product vocabulary. Authoritative definitions; the reader's lexicon
layer must not redefine these terms.

Also see the table form in [reference/glossary.md](./reference/glossary.md) and SRS §16.

### ADI

Average Demand Interval - intermittence measure used in Syntetos-Boylan classification (SBC).

### ABC-XYZ

Inventory classification by value (ABC) and demand variability (XYZ).

### Analytics run

One execution of an analytics job, recorded as a row in `analytics_runs`.

### APScheduler

In-process job scheduler used instead of Celery (ADR-004).

### Champion

Selected forecasting method for a series; must beat Seasonal Naive on MASE.

### Conformal interval

Calibration wrapper for prediction intervals (ADR-025).

### CV

Rolling-origin cross-validation for forecast methods.

### Diataxis

Documentation system with four modes: tutorials, how-to, reference, and explanation.

### Digest

Scheduled email summarizing alerts for managers.

### FR / NFR / DS / DAT / SEC

Requirement ID prefixes in the SRS (functional, non-functional, data science, data, security).

### httpOnly refresh

Refresh token stored only in a non-JS-readable cookie (SameSite=Strict).

### Inventory intel

Reorder, risk, and anomaly outputs from the inventory analytics job.

### MASE

Mean Absolute Scaled Error - primary forecast accuracy metric.

### OpenAPI client

Generated TypeScript client in `packages/api-client`.

### PSI

Population Stability Index - lead-score drift detector.

### RBAC

Role-based access control with deny-by-default permissions.

### RFM

Recency, Frequency, Monetary customer segmentation.

### SBC

Syntetos-Boylan Classification of demand patterns (smooth, intermittent, erratic, lumpy).

### Seasonal Naive

Mandatory forecasting baseline and champion floor.

### Stock movement

Append-only inventory ledger entry.

### Unit risk

Per-vehicle-unit aging / survival risk score.
