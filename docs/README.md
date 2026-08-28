# DealerIQ documentation

**Audience:** engineers, operators, auditors, and portfolio reviewers.  
**Last updated:** 2026-07-17  
**Layout:** [Diataxis](https://diataxis.fr/) - tutorials, how-to guides, reference, explanation.

The authoritative requirements document remains [`srs/DealerIQ-SRS.md`](srs/DealerIQ-SRS.md)
(DIQ-SRS-001). Architecture decisions live in [`adr/`](adr/). Phase planning under
[`../specs/`](../specs/) is a **planning archive**; what actually shipped is recorded in
[`../CHANGELOG.md`](../CHANGELOG.md).

Markdown in this tree is the source of truth. The interactive handbook reader
(`docs-app/`, ADR-028) indexes it: `make docs` locally, or `/handbook/` after
`make docs-site`. Start studying at [`00-reading-path.md`](00-reading-path.md).

## Start here

| If you want to... | Go to |
|-----------------|-------|
| Study the handbook (3 sessions) | [Reading path](00-reading-path.md) |
| Browse the interactive reader | `make docs` → http://localhost:5178 · or `/handbook/` |
| Run the app for the first time | [Getting started - onboarding](getting-started/onboarding.md) |
| Day-to-day local development | [Runbook: local-dev](runbooks/local-dev.md) |
| Understand the system | [Explanation - architecture](explanation/architecture.md) |
| See system diagrams | [Visual catalog](diagrams/README.md) |
| Look up a term | [Glossary](glossary.md) |
| Look up an env var | [Reference - configuration](reference/configuration.md) |
| Call the API | [Reference - API](reference/api.md) + live OpenAPI at `/api/v1/docs` |
| See who can do what | [Reference - permissions](reference/permissions.md) |
| Deploy / back up production | [Runbooks](runbooks/) |

## Tutorials (getting started)

- [Onboarding](getting-started/onboarding.md) - bootstrap, seed, first login, role tour

## How-to guides

- [Regenerate the API client](how-to/regenerate-api-client.md)
- [Trigger analytics jobs](how-to/trigger-jobs.md)
- [Deploy to production](how-to/deploy.md) (pointer to runbooks)

## Reference

- [Configuration / environment variables](reference/configuration.md)
- [API guide](reference/api.md)
- [OpenAPI snapshot](reference/openapi.json) (regenerate with `make docs-openapi`)
- [RBAC permission matrix](reference/permissions.md)
- [Glossary](glossary.md) ([table form](reference/glossary.md))

## Explanation (concepts)

- [Architecture](explanation/architecture.md)
- [Security model](explanation/security-model.md)
- [Domain lifecycles](explanation/domain-lifecycles.md) - orders, leads, alerts
- [Analytics pipeline](explanation/analytics-pipeline.md)
- [Data model](explanation/data-model.md)

## Diagrams

- [Visual documentation catalog](diagrams/README.md) - Mermaid D01-D18 (context, deploy, auth, state machines, ER, CI)

## Operational runbooks

- [Local development](runbooks/local-dev.md)
- [Jobs and alerts](runbooks/jobs-and-alerts.md)
- [Production deploy](runbooks/production-deploy.md)
- [Data durability (EBS + S3)](runbooks/durability.md)
- [Incident response](runbooks/incident-response.md)
- [Rollback](runbooks/rollback.md)

## Durable product & research corpus

| Path | Role |
|------|------|
| [srs/](srs/) | Software requirements specification |
| [diagrams/](diagrams/) | Mermaid visual catalog (D01-D18) |
| [adr/](adr/) | Architecture decision records ([index](adr/README.md)) |
| [paper/](paper/) | Forecasting benchmark manuscript |
| [backlog.md](backlog.md) | Deferred P1/P2 items |

## Planning archive (not product docs)

[`specs/`](../specs/) holds the `spec.md` / `plan.md` / `tasks.md` per delivery phase.
Prefer the CHANGELOG for "what is true today."

## Project governance

- Constitution: [`docs/constitution.md`](constitution.md)
- Contributing: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- Security disclosure: [`../SECURITY.md`](../SECURITY.md)
