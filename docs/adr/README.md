# Architecture Decision Records

Indexed decisions for DealerIQ. Status is recorded in each file.

## Index

- [`001-monorepo.md`](001-monorepo.md) — Single Monorepo
- [`002-fastapi-over-django.md`](002-fastapi-over-django.md) — FastAPI over Django
- [`003-postgresql-16.md`](003-postgresql-16.md) — PostgreSQL 16
- [`004-apscheduler-not-celery.md`](004-apscheduler-not-celery.md) — APScheduler (not Celery) for local job scheduling
- [`005-forecasting-libraries.md`](005-forecasting-libraries.md) — statsforecast for classical forecasting methods
- [`006-backend-owned-auth.md`](006-backend-owned-auth.md) — Backend-owned auth (JWT + refresh rotation) over NextAuth
- [`007-recharts.md`](007-recharts.md) — Recharts for visualization
- [`008-alembic-no-autocreate.md`](008-alembic-no-autocreate.md) — Alembic migrations only, no auto-create
- [`009-argon2id-parameters.md`](009-argon2id-parameters.md) — Argon2id parameters
- [`010-jwt-library.md`](010-jwt-library.md) — JWT library — PyJWT
- [`011-sqlalchemy-alembic-policy.md`](011-sqlalchemy-alembic-policy.md) — SQLAlchemy 2.0 typed declarative + Alembic autogenerate-then-review
- [`012-api-client-generator.md`](012-api-client-generator.md) — API client generator — openapi-typescript + openapi-fetch
- [`013-postgres-test-strategy.md`](013-postgres-test-strategy.md) — Postgres test strategy — testcontainers for CI/integration, Compose for dev
- [`014-frontend-data-fetching.md`](014-frontend-data-fetching.md) — Frontend data fetching — TanStack Query over the generated client
- [`015-python-packaging.md`](015-python-packaging.md) — Python packaging — uv workspaces
- [`016-js-monorepo-tooling.md`](016-js-monorepo-tooling.md) — JS monorepo tooling — npm workspaces
- [`017-survival-and-outlier-libraries.md`](017-survival-and-outlier-libraries.md) — `lifelines` for Kaplan-Meier; hand-implemented, unit-tested GESD
- [`018-narrow-statsmodels-to-stl.md`](018-narrow-statsmodels-to-stl.md) — Narrow statsmodels' role to STL only
- [`019-refresh-token-rotation-algorithm.md`](019-refresh-token-rotation-algorithm.md) — Refresh-token rotation with reuse detection
- [`020-rate-limiting.md`](020-rate-limiting.md) — Rate limiting — slowapi, in-memory
- [`021-synthetic-demand-volume-vs-sbc-coverage.md`](021-synthetic-demand-volume-vs-sbc-coverage.md) — Synthetic demand volume vs. SBC-class-coverage tradeoff
- [`022-rfm-segment-mapping.md`](022-rfm-segment-mapping.md) — RFM segment-name mapping
- [`023-lead-scoring-model-design.md`](023-lead-scoring-model-design.md) — Lead-scoring model — isotonic calibration, retrain-fresh-per-run, inline drift check
- [`024-achieved-accuracy-and-sales-target.md`](024-achieved-accuracy-and-sales-target.md) — Achieved-accuracy dedup rule; a single configurable sales target, not per-salesperson quotas
- [`025-conformal-intervals-for-interval-native-methods.md`](025-conformal-intervals-for-interval-native-methods.md) — Conformal prediction intervals for the four DS-FC-003 methods with no native interval estimator
- [`026-production-data-durability.md`](026-production-data-durability.md) — Production data durability — EBS bind-mount + S3 backups
- [`027-internal-layout-and-docs-portal.md`](027-internal-layout-and-docs-portal.md) — Internal layout refinement and Diataxis docs portal
- [`028-handbook-reader.md`](028-handbook-reader.md) — Interactive handbook reader (`docs-app`) at `/handbook/`
