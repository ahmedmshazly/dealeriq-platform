# API reference guide

**Audience:** API consumers and frontend engineers.  
**Last updated:** 2026-07-17  
**Refs:** SRS §8, Principle VI, ADR-012

## Sources of truth

| Artifact | Role |
|----------|------|
| Live OpenAPI | `GET /api/v1/openapi.json` (development only) |
| Swagger UI | `http://localhost:8000/api/v1/docs` (development only) |
| Committed snapshot | [`openapi.json`](openapi.json) — `make docs-openapi` |
| TypeScript client | `packages/api-client` — only sanctioned web→API path |

Production disables OpenAPI/docs URLs when `APP_ENV` ≠ `development`.

## Versioning

All business routes are under **`/api/v1`**. Breaking contract changes require a deliberate
version bump and regenerated client (QA-005). Health probes:

- `GET /api/v1/health` — liveness
- `GET /api/v1/ready` — readiness (DB)

## Authentication

1. `POST /api/v1/auth/login` → access JWT in body; refresh token in httpOnly cookie.
2. Send `Authorization: Bearer <access>` on subsequent requests.
3. `POST /api/v1/auth/refresh` (cookie) rotates refresh + returns new access.
4. `POST /api/v1/auth/logout` clears refresh.

## Error envelope

All handled API errors:

```json
{
  "error": {
    "code": "forbidden",
    "message": "You do not have permission to perform this action.",
    "details": []
  }
}
```

| HTTP | `error.code` | Meaning |
|------|--------------|---------|
| 400 | `bad_request` | Domain rejection |
| 401 | `unauthorized` | Missing/invalid auth |
| 403 | `forbidden` | Missing permission |
| 403 | `password_change_required` | Must change password |
| 404 | `not_found` | Missing resource |
| 409 | `conflict` | State conflict (e.g. job running) |
| 422 | `validation_error` | Pydantic/request validation (`details` = FastAPI errors) |

## Authorization

Routes declare permissions such as `orders:view`, `jobs:trigger`. See
[permissions.md](permissions.md). Missing permission → `403 forbidden`.

## Resource map (outline)

| Prefix | Purpose |
|--------|---------|
| `/auth/*` | Login, refresh, logout, change-password, me |
| `/users`, `/roles`, `/permissions` | Admin RBAC |
| `/audit-log` | Audit browse |
| `/branches`, `/vehicle-models`, `/vehicle-units` | Inventory |
| `/customers`, `/leads`, `/orders` | CRM / sales |
| `/forecasts`, `/inventory-intel` | Analytics read APIs |
| `/jobs/*` | Trigger + run history |
| `/alerts`, `/alert-rules` | Notifications + rule config |
| `/dashboards/*`, `/reports/*` | Manager/Sales dashboards & monthly report |

Exact paths, schemas, and enums: OpenAPI / generated client.

## Client usage (web)

```ts
import { api } from "@/lib/api";
const { data, error } = await api.GET("/api/v1/orders");
```

Do not add hand-rolled `fetch` to undocumented endpoints (except the documented refresh-cookie
path in auth).
