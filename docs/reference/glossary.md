# Glossary

**Audience:** all readers.  
**Last updated:** 2026-07-17  
**Also see:** SRS §16 · handbook form [`../glossary.md`](../glossary.md) (authoritative for the reader lexicon layer)

| Term | Meaning |
|------|---------|
| **ADI** | Average Demand Interval - intermittence measure for SBC |
| **ABC-XYZ** | Inventory classification by value (ABC) and demand variability (XYZ) |
| **Analytics run** | One execution of a job, row in `analytics_runs` |
| **APScheduler** | In-process job scheduler used instead of Celery (ADR-004) |
| **Champion** | Selected forecasting method for a series; must beat Seasonal Naive on MASE |
| **Conformal interval** | Calibration wrapper for prediction intervals (ADR-025) |
| **CV** | Rolling-origin cross-validation for forecast methods |
| **Diataxis** | Docs system: tutorials / how-to / reference / explanation |
| **Digest** | Scheduled email summarizing alerts |
| **FR / NFR / DS / DAT / SEC** | Requirement ID prefixes in the SRS |
| **httpOnly refresh** | Refresh token stored only in a non-JS-readable cookie |
| **Inventory intel** | Reorder, risk, anomaly outputs from the inventory job |
| **MASE** | Mean Absolute Scaled Error - primary forecast accuracy metric |
| **OpenAPI client** | Generated TS client in `packages/api-client` |
| **PSI** | Population Stability Index - lead-score drift detector |
| **RBAC** | Role-based access control (deny-by-default permissions) |
| **RFM** | Recency, Frequency, Monetary customer segmentation |
| **SBC** | Syntetos-Boylan Classification of demand patterns |
| **Seasonal Naive** | Mandatory forecasting baseline / champion floor |
| **Stock movement** | Append-only inventory ledger entry |
| **Unit risk** | Per-vehicle-unit aging / survival risk score |

Product roles: **Admin**, **Manager**, **Sales**, **Analyst** - see
[permissions.md](permissions.md).
