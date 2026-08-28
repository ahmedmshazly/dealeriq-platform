# Implementation Plan: Core Domain

**Branch**: `003-core-domain` | **Date**: 2026-07-10 | **Spec**: `specs/003-core-domain/spec.md`

## Summary

Build the transactional core: branches, vehicle models/units with an append-only stock-movement
ledger, customers, leads with a validated state machine, and the full order lifecycle with
threshold-based approval and atomic unit reservation. Implemented as three internal checkpoints
under one spec/plan (per the constitution's "one spec, multiple checkpoints" pattern for
oversized phases), each gated on green tests before moving to the next: **(A) inventory**,
**(B) customers/leads**, **(C) orders**.

## Deviation note: the ownership-check mechanism

Phase 1's plan.md said the FR-012 ownership-check mechanism would be "implemented and
unit-tested generically" in Phase 1 itself. In practice there was nothing to check ownership
*of* until leads/orders existed, so it's built here instead, in `auth/ownership.py`, as soon as
the first owned resources (leads, then orders) exist. This is noted here rather than silently
diverging from what Phase 1 said.

## Permission set added this phase

Extends the Phase 1 table (migration `0002_core_domain`):

| Permission key | Admin | Manager | Sales | Analyst |
|---|---|---|---|---|
| `inventory:view` | ✓ | ✓ | ✓ | ✓ |
| `inventory:manage` | ✓ | ✓ | | |
| `customers:view` | ✓ | ✓ | ✓ | ✓ |
| `customers:manage` | ✓ | ✓ | ✓ | |
| `leads:view` | ✓ | ✓ | ✓ | ✓ |
| `leads:manage_own` | | | ✓ | |
| `leads:manage_any` | ✓ | ✓ | | |
| `orders:view` | ✓ | ✓ | ✓ | ✓ |
| `orders:manage_own` | | | ✓ | |
| `orders:manage_any` | ✓ | ✓ | | |
| `orders:approve` | ✓ | ✓ | | |
| `orders:view_margin` | ✓ | ✓ | | |

Ownership check (`auth/ownership.py`): a route requires the `*_own` OR `*_any` permission to be
callable at all; the service layer then checks `has_any_permission or resource.owner_id ==
current_user.id`, else 403. Unit-tested in isolation (no DB) against a fake resource/permission
set, then exercised end-to-end in the leads and orders integration tests.

## Data model (this phase's migration `0002_core_domain`)

- **branches**(id, name, city)
- **vehicle_models**(id, make, model, trim, segment, list_price)
- **vehicle_units**(id, vin unique, model_id FK, branch_id FK, status
  enum[in_stock,reserved,sold,transferred] via CHECK, acquisition_date, acquisition_cost)
- **stock_movements**(id, unit_id FK, type enum[receipt,reservation,sale,transfer,adjustment],
  from_branch_id FK nullable, to_branch_id FK nullable, actor_id FK, reason nullable, occurred_at),
  append-only, DAT-003
- **customers**(id, name, phone, email, city, source_channel)
- **leads**(id, customer_id FK, model_id FK, budget_band, status
  enum[new,contacted,test_drive,negotiating,won,lost] via CHECK, owner_id FK, last_activity_at)
- **lead_events**(id, lead_id FK, type, notes, actor_id FK, at) - activity/state-change log
- **orders**(id, customer_id FK, unit_id FK, salesperson_id FK, negotiated_price, discount,
  payment_type enum[cash,finance], status
  enum[draft,pending_approval,approved,delivered,cancelled] via CHECK)
- **order_events**(id, order_id FK, from_status, to_status, actor_id FK, reason nullable, at)

Indices (DAT-004 pattern): `orders(created_at)`, `stock_movements(unit_id, occurred_at)`,
`leads(owner_id, status)`, `orders(salesperson_id, status)`.

Status enums use `sa.Enum(..., native_enum=False)` (VARCHAR + CHECK constraint) for the same
portability reason as any future custom-value extension, consistent with how Phase 1 treated
`roles.key` - except here the value set is genuinely fixed by the SRS (not meant to be
end-user-extensible), so a CHECK constraint is the correct DAT-002 mechanism, unlike roles.

## Lead state machine

`new → {contacted, lost}`, `contacted → {test_drive, negotiating, lost}`,
`test_drive → {negotiating, lost}`, `negotiating → {won, lost}`; `won`/`lost` are terminal. Lost
is reachable from any non-terminal state (real sales funnels abandon at any stage) but never
skips forward. Implemented as a pure function (`domain/lead_state_machine.py`) unit-tested
against every legal and illegal transition pair before being wired into the route.

## Order lifecycle

`draft → pending_approval|approved → delivered`, `→ cancelled` from `approved`. Submitting a
draft computes `discount / list_price`; ≤ the configurable threshold (`order_approval_threshold`
setting, default 0.05) auto-approves, else `pending_approval`. Approving an order and reserving
the unit happen in one DB transaction (`SELECT ... FOR UPDATE` on the unit row) so two concurrent
approval attempts on the same unit can't both succeed (spec's concurrency edge case). Delivering
marks the unit `sold` and appends a `sale` stock_movement in the same transaction as the order's
status change.

## API endpoints (this phase)

- `GET/POST/PATCH /api/v1/branches`, `/vehicle-models`, `/vehicle-units` (`inventory:view`/
  `inventory:manage`); `POST /vehicle-units/{id}/adjust` (mandatory reason, FR-024)
- `GET/POST/PATCH /api/v1/customers` (`customers:view`/`customers:manage`)
- `GET/POST /api/v1/leads`, `POST /api/v1/leads/{id}/transition` (`leads:view`/`leads:manage_own`/
  `leads:manage_any`)
- `GET/POST /api/v1/orders`, `POST /api/v1/orders/{id}/submit|approve|deliver|cancel`
  (`orders:view`/`orders:manage_own`/`orders:manage_any`/`orders:approve`); margin field
  included only when `orders:view_margin` is granted

## Constitution Check

- Principle IV: `stock_movements`/`order_events`/`lead_events` are append-only from their first
  row; one reviewed migration, autogenerate-then-review (ADR-011).
- Principle III: every new route uses `require_permission`/the new ownership helper; nothing
  bypasses it.
- Principle VII: ≥80% coverage target; state machines and the approval-threshold/atomic-
  reservation logic get unit + integration tests before being trusted.
- No violations requiring Complexity Tracking.

## Project Structure (additions)

```text
apps/api/src/dealeriq_api/
├── auth/ownership.py
├── domain/models/{branch,vehicle,customer,lead,order}.py
├── domain/lead_state_machine.py
├── domain/order_service.py, lead_service.py, inventory_service.py, customer_service.py
└── routes/{branches,vehicle_models,vehicle_units,customers,leads,orders}.py

apps/web/
├── app/(authenticated)/inventory/page.tsx
├── app/(authenticated)/customers/page.tsx
├── app/(authenticated)/leads/page.tsx
├── app/(authenticated)/orders/{page.tsx,[id]/page.tsx}
└── components/ui/{data-table,select}.tsx (shared table primitive, used by all four list pages)
```

## Complexity Tracking

None.
