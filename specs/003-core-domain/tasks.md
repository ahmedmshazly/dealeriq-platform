# Tasks: Core Domain

**Input**: plan.md from `specs/003-core-domain/`. Organized as three gated checkpoints.

## Checkpoint A — Inventory

- [ ] T001 `domain/models/branch.py`, `domain/models/vehicle.py` (VehicleModel, VehicleUnit,
      StockMovement)
- [ ] T002 Migration `0002_core_domain` (start): branches, vehicle_models, vehicle_units,
      stock_movements + new inventory/customers/leads/orders permission set (table added to
      incrementally across this migration as models are written — one migration for the whole
      phase, reviewed once at the end per ADR-011)
- [ ] T003 `domain/inventory_service.py`: create model/unit, list w/ filter+sort+pagination
      (API-001), stock adjustment (mandatory reason, FR-024), days-on-lot computed property
- [ ] T004 `routes/vehicle_models.py`, `routes/vehicle_units.py`, `routes/branches.py`
- [ ] T005 Tests: unit (days-on-lot calc), integration (create/list/filter, adjustment writes
      ledger + audit row, `inventory:view` vs `inventory:manage` 403)
- [ ] T006 Frontend: `app/(authenticated)/inventory/page.tsx` (filterable/paginated table,
      create-unit form)
- [ ] Checkpoint gate: `make test` + `make lint` green before Checkpoint B

## Checkpoint B — Customers & Leads

- [ ] T007 `domain/models/customer.py`, `domain/models/lead.py` (Lead, LeadEvent)
- [ ] T008 `domain/lead_state_machine.py`: pure transition-validation function
- [ ] T009 `auth/ownership.py`: generic owner-or-permission check
- [ ] T010 `domain/customer_service.py` (dedup warning on phone/email match, FR-030),
      `domain/lead_service.py` (create, list, transition w/ state machine + ownership)
- [ ] T011 `routes/customers.py`, `routes/leads.py`
- [ ] T012 Tests: unit (state machine — every legal/illegal transition pair; ownership helper in
      isolation), integration (dedup warning, invalid transition rejected, Sales-edit-own-only
      403 for another Sales user's lead, Manager-edit-any succeeds)
- [ ] T013 Frontend: `app/(authenticated)/customers/page.tsx`, `app/(authenticated)/leads/page.tsx`
- [ ] Checkpoint gate: `make test` + `make lint` green before Checkpoint C

## Checkpoint C — Orders

- [ ] T014 `domain/models/order.py` (Order, OrderEvent)
- [ ] T015 `domain/order_service.py`: create (draft), submit (threshold check → auto-approve or
      pending_approval), approve (atomic unit reservation via `SELECT ... FOR UPDATE`), deliver
      (mark unit sold + `sale` stock_movement, same transaction), cancel (release reservation,
      mandatory reason)
- [ ] T016 `routes/orders.py`; margin field conditionally serialized based on
      `orders:view_margin`
- [ ] T017 Tests: unit (threshold auto-approve vs pending_approval boundary), integration (full
      lifecycle draft→submit→approve→deliver with ledger assertions at each step, concurrent
      approval-on-same-unit conflict, cancel releases reservation + requires reason, margin
      present/absent by role)
- [ ] T018 Frontend: `app/(authenticated)/orders/page.tsx` (list), `orders/[id]/page.tsx` (detail
      + timeline + approve/deliver/cancel actions)
- [ ] T019 Regenerate `packages/api-client`; confirm it compiles

## Phase close-out

- [ ] T020 Exit demo: full order lifecycle with ledger + approvals in the UI (SRS §13 Phase 2)
- [ ] T021 Re-verify `make bootstrap && make seed && make dev` (NFR-007) and `make ci`
