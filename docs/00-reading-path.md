---
title: Reading path
description: Three sittings to learn DealerIQ — onboarding, architecture/security, analytics/ops.
last-verified: 2026-07-17
---

# Reading path - start here

How to study the DealerIQ handbook. Three sittings; then the rest is reference.

## Session 1 - onboarding

Bootstrap the stack, sign in, and know where day-to-day runbooks live.

| Document | Estimate |
|---|---|
| [Onboarding](./getting-started/onboarding.md) | ~15 min |
| [Local development](./runbooks/local-dev.md) | ~10 min |
| [Docs portal](./README.md) | ~5 min |

## Session 2 - architecture and security

Know the system shape, trust boundary, and who can do what.

| Document | Estimate |
|---|---|
| [Architecture](./explanation/architecture.md) | ~20 min |
| [Security model](./explanation/security-model.md) | ~15 min |
| [Permissions](./reference/permissions.md) | ~10 min |
| [Visual catalog](./diagrams/README.md) | ~10 min |

## Session 3 - analytics and operations

Forecasting jobs, domain lifecycles, and how to run / recover production.

| Document | Estimate |
|---|---|
| [Analytics pipeline](./explanation/analytics-pipeline.md) | ~15 min |
| [Domain lifecycles](./explanation/domain-lifecycles.md) | ~12 min |
| [Data model](./explanation/data-model.md) | ~10 min |
| [Production deploy](./runbooks/production-deploy.md) | ~10 min |
| [Jobs and alerts](./runbooks/jobs-and-alerts.md) | ~8 min |

## Checkpoints

1. **What is the one command path to a seeded local stack?**
   → [Onboarding](./getting-started/onboarding.md)

2. **Where is the API security boundary, and what does deny-by-default mean?**
   → [Security model](./explanation/security-model.md)

3. **How do analytics jobs avoid concurrent double-runs?**
   → [Analytics pipeline](./explanation/analytics-pipeline.md)

4. **What Mermaid diagram shows login + authenticated request?**
   → [Visual catalog](./diagrams/README.md)

5. **Where do production backups land, and what restores them?**
   → [Production deploy](./runbooks/production-deploy.md)
