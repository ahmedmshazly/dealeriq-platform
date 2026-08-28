# Tasks: Core Domain

**Input**: plan.md from `specs/003-core-domain/`. Organized as three gated checkpoints.

## Checkpoint A - Inventory

- [x] T001 `domain/models/branch.py`, `domain/models/vehicle.py` (VehicleModel, VehicleUnit,
      StockMovement)
- [x] T002 Migration for branches, vehicle_models, vehicle_units, stock_movements + inventory
      permission set. Split into one migration per checkpoint (0002a/b/c) rather than a single
      combined migration - see phase report deviation note.
- [x] T003 `domain/inventory_service.py`: create model/unit, list w/ filter+sort+pagination
      (API-001), stock adjustment (mandatory reason, FR-024), days-on-lot computed property
- [x] T004 `routes/vehicle_models.py`, `routes/vehicle_units.py`, `routes/branches.py`
- [x] T005 Tests: unit (days-on-lot calc), integration (create/list/filter, adjustment writes
      ledger + audit row, `inventory:view` vs `inventory:manage` 403)
- [x] T006 Frontend: `app/(authenticated)/inventory/page.tsx` (filterable table, create-branch/
      model/unit forms, transfer adjustment action)
- [x] Checkpoint gate: `make test` + `make lint` green before Checkpoint B

## Checkpoint B - Customers & Leads

- [x] T007 `domain/models/customer.py`, `domain/models/lead.py` (Lead, LeadEvent)
- [x] T008 `domain/lead_state_machine.py`: pure transition-validation function
- [x] T009 `auth/ownership.py`: generic owner-or-permission check (`may_act_on` pure function +
      `assert_owner_or_permission`/`require_any_permission` DB-touching wrappers)
- [x] T010 `domain/customer_service.py` (dedup warning on phone/email match, FR-030),
      `domain/lead_service.py` (create, list, transition w/ state machine + ownership)
- [x] T011 `routes/customers.py`, `routes/leads.py`
- [x] T012 Tests: unit (state machine - every legal/illegal transition pair, parametrized; the
      ownership helper's pure decision function in isolation), integration (dedup warning,
      invalid transition rejected, Sales-edit-own-only 403 for another Sales user's lead,
      Manager-edit-any succeeds, Sales cannot create a lead owned by someone else)
- [x] T013 Frontend: `app/(authenticated)/customers/page.tsx`, `app/(authenticated)/leads/page.tsx`
      (state-machine-aware transition buttons)
- [x] Checkpoint gate: `make test` + `make lint` green before Checkpoint C

## Checkpoint C - Orders

- [x] T014 `domain/models/order.py` (Order, OrderEvent)
- [x] T015 `domain/order_service.py`: create (draft), submit (threshold check → auto-approve or
      pending_approval), approve (atomic unit reservation via `SELECT ... FOR UPDATE`), deliver
      (mark unit sold + `sale` stock_movement, same transaction), cancel (release reservation
      from `approved`, or close out with no ledger change from `pending_approval` - see phase
      report deviation note - mandatory reason either way)
- [x] T016 `routes/orders.py` incl. `GET /{id}`, `GET /{id}/timeline` (FR-044, not in the
      original endpoint list); margin field conditionally serialized based on
      `orders:view_margin`
- [x] T017 Tests: unit (threshold auto-approve vs pending_approval boundary via the real
      `_discount_fraction` math), integration (full lifecycle draft→submit→approve→deliver with
      ledger assertions at each step, double-approval rejected as a sequential proxy for the
      concurrency guard - see phase report on why a true concurrent test wasn't attempted, cancel
      releases reservation + requires reason, margin present/absent by role, ownership checks)
- [x] T018 Frontend: `app/(authenticated)/orders/page.tsx` (list + create), `orders/[id]/page.tsx`
      (detail + timeline + submit/approve/deliver/cancel actions)
- [x] T019 Regenerate `packages/api-client`; confirm it compiles

## Phase close-out

- [x] T020 Exit demo: full order lifecycle with ledger + approvals in the UI (SRS §13 Phase 2) -
      verified in a real browser end-to-end, both the auto-approve and Manager-approval paths,
      plus the Sales-cannot-approve 403 and margin-by-role checks; see phase report.
- [x] T021 Re-verify `make bootstrap && make seed && make dev` (NFR-007) and `make ci`
