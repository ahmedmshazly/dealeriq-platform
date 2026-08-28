# RBAC permission matrix

**Audience:** admins, security reviewers.  
**Last updated:** 2026-07-17  
**Source:** Alembic permission seeds (auth + domain migrations)  
**Visual:** [D09 RBAC flow](../explanation/security-model.md#d09-rbac-deny-by-default) · [diagram catalog](../diagrams/README.md)

Roles: **admin**, **manager**, **sales**, **analyst**. Keys are `resource:action` strings.

Legend: **Y** = granted by seed migrations; blank = not granted.

| Permission | Admin | Manager | Sales | Analyst |
|------------|:-----:|:-------:|:-----:|:-------:|
| `users:view` | Y | Y | | |
| `users:manage` | Y | | | |
| `permissions:view` | Y | | | |
| `audit_log:view` | Y | | | |
| `inventory:view` | Y | Y | Y | Y |
| `inventory:manage` | Y | Y | | |
| `customers:view` | Y | Y | Y | Y |
| `customers:manage` | Y | Y | Y | |
| `leads:view` | Y | Y | Y | Y |
| `leads:manage_own` | | | Y | |
| `leads:manage_any` | Y | Y | | |
| `orders:view` | Y | Y | Y | Y |
| `orders:manage_own` | | | Y | |
| `orders:manage_any` | Y | Y | | |
| `orders:approve` | Y | Y | | |
| `orders:view_margin` | Y | Y | | |
| `jobs:trigger` | Y | | | |
| `jobs:view` | Y | | | |
| `forecasts:view` | Y | Y | | Y |
| `inventory-intel:view` | Y | Y | | Y |
| `alerts:view` | Y | Y | Y | Y |
| `alerts:manage` | Y | Y | | |
| `alert-rules:manage` | Y | Y | | |
| `dashboard:view_manager` | Y | Y | | |
| `dashboard:view_sales` | Y | Y | Y | |

Sales **write** paths additionally use ownership helpers (`assert_owner_or_permission`). List/read
endpoints that only check `*:view` may return peer rows - see
the CHANGELOG for audit notes vs product intent.

## How to inspect live

Admin UI: `/admin/permissions`, or `GET /api/v1/permissions` with `permissions:view`.

## Changing grants

Add a new Alembic revision that inserts into `permissions` / `role_permissions`. Do not edit
historical migrations. Document in an ADR if the security model changes.
