# Feature Specification: Core Domain

**Feature Branch**: `003-core-domain`

**Created**: 2026-07-10

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 2 - "FR-020..045, DAT-001..004, API-001..003"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inventory is tracked as an immutable ledger (Priority: P1)

As a Manager, I create vehicle models and receive vehicle units into stock; every change in a
unit's status (received, reserved, sold, transferred, adjusted) is recorded permanently, and
current stock is always derived from that history, never overwritten.

**Why this priority**: Everything downstream (orders, forecasting in later phases) depends on
inventory state being trustworthy and auditable.

**Independent Test**: Create a model, receive three units, sell one via the order flow, confirm
`stock_movements` has one row per event and the unit's displayed status matches the latest
movement.

**Acceptance Scenarios**:

1. **Given** a Manager, **When** they create a vehicle model and add a unit by VIN, **Then** a
   `receipt` stock movement is recorded and the unit shows `in_stock` (FR-020, FR-021).
2. **Given** an in-stock unit, **When** its status changes via any path (reservation, sale,
   transfer, adjustment), **Then** a new stock_movements row is appended - existing rows are
   never edited (DAT-003).
3. **Given** the inventory list, **When** filtered by branch/model/segment/status/days-on-lot
   bucket, **Then** results are paginated and sorted correctly (FR-022, API-001).

---

### User Story 2 - Customers, leads, and a validated funnel (Priority: P1)

As a Sales user, I create customers and leads, and the system prevents me from making invalid
status jumps (e.g., `new` straight to `won`).

**Why this priority**: The lead funnel is the input to the conversion-scoring model that arrives
in Phase 7 - its state machine has to be correct now.

**Independent Test**: Attempt an invalid transition (`new` → `won`) and confirm it's rejected;
attempt each valid transition and confirm it succeeds.

**Acceptance Scenarios**:

1. **Given** a new customer with a phone/email matching an existing customer, **When** created,
   **Then** the system warns of a likely duplicate without blocking creation (FR-030).
2. **Given** a lead in `negotiating`, **When** transitioned to `won`, **Then** it succeeds; **When**
   attempted from `new` directly, **Then** it's rejected with a clear error (FR-031).
3. **Given** a Sales user who does not own a lead, **When** they attempt to edit it, **Then** they
   get 403; **given** the same lead, **when** a Manager edits it, **then** it succeeds (FR-012).

---

### User Story 3 - The full order lifecycle, with ledger integrity and approval gating (Priority: P1)

As a Sales user, I create an order linking a customer to a specific vehicle unit; if my discount
exceeds the threshold it requires Manager approval; approving reserves the unit atomically;
delivering marks it sold and appends the ledger row; margin is visible only to Manager+.

**Why this priority**: This is the phase's stated exit demo and the single most
business-critical workflow in the whole product.

**Independent Test**: Create an order with a >5% discount as Sales; confirm it's
`pending_approval` and the unit is NOT yet reserved; approve as Manager; confirm the unit is now
`reserved`; deliver; confirm the unit is `sold` and a `sale` stock movement exists.

**Acceptance Scenarios**:

1. **Given** a discount ≤ the configured threshold (default 5% of list price), **When** an order
   is submitted, **Then** it auto-approves (FR-041).
2. **Given** a discount above the threshold, **When** submitted, **Then** it becomes
   `pending_approval` and requires a Manager/Admin decision (FR-041).
3. **Given** an approved order, **When** delivered, **Then** the unit is marked `sold` and the
   ledger records a `sale` movement atomically with the order's status change (FR-042).
4. **Given** an order's margin (negotiated price - acquisition cost), **When** viewed by a Sales
   user, **Then** it is not present in the response at all; **when** viewed by Manager+, **then**
   it is (FR-043).
5. **Given** an approved order, **When** cancelled, **Then** the unit's reservation is released
   and a reason is required (FR-045).

### Edge Cases

- What happens when two orders are submitted for the same unit concurrently? → the unit's
  status is checked at approval time inside the same transaction that reserves it; the second
  approval fails with a conflict rather than double-booking.
- What happens when a lead's owner is deactivated? → the lead keeps its `owner_id`; only an
  Admin/Manager reassignment (not built this phase - FR-034 bulk reassignment is backlogged)
  changes it.
- What happens when a stock adjustment has no reason? → rejected (FR-024, mandatory reason).

## Requirements *(mandatory)*

### Functional Requirements

Inventory: FR-020 (create/edit models & units), FR-021 (append-only stock_movements, derived
stock), FR-022 (filter/sort/paginate), FR-023 (computed days-on-lot; ABC/XYZ/aging-risk fields
exist on the schema now, populated once analytics land in Phase 5 - see Assumptions), FR-024
(stock adjustment with mandatory reason, audit-logged).

Customers & Leads: FR-030 (create/edit customers, dedup warning), FR-031 (leads with a validated
state machine), FR-032 (conversion score/explanation fields exist on the schema now, populated
once DS-CUST-003 lands in Phase 7 - see Assumptions), FR-033 (RFM segment display - same),
FR-012 (Sales edit-own, Manager/Admin edit-any, for leads and orders).

Orders: FR-040 (create order: customer + specific unit + price/discount/payment_type/status),
FR-041 (auto-approve under threshold, else pending_approval), FR-042 (approve reserves
atomically; deliver marks sold + ledger row), FR-043 (margin visible Manager+ only), FR-044
(order timeline), FR-045 (cancel approved releases reservation, requires reason).

Cross-cutting: DAT-001..004 (Alembic-only, FK/CHECK integrity, analytics/transactional
separation - N/A until Phase 3+ analytics tables exist, but the principle is upheld by never
writing analytics tables here; required indices), API-001..003 (pagination/filter/sort on all
list endpoints, idempotency-safe mutations, rate limiting already covers auth per Phase 1).

### Key Entities

**Branch**, **VehicleModel**, **VehicleUnit**, **StockMovement** (append-only), **Customer**,
**Lead**, **LeadEvent**, **Order**, **OrderEvent**.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Full order lifecycle (draft → pending_approval/approved → delivered) works in the
  UI end-to-end with correct ledger rows at each step.
- **SC-002**: An invalid lead-status transition is rejected with a clear error; every valid
  transition succeeds.
- **SC-003**: A Sales user cannot edit another Sales user's lead/order (403); a Manager can edit
  any.
- **SC-004**: Order margin is absent from API responses for Sales/Analyst, present for
  Manager/Admin.
- **SC-005**: `make ci` stays green; new domain code carries ≥80% coverage.

## Assumptions

- FR-023's ABC/XYZ class and aging-risk score, and FR-032/033's conversion score and RFM
  segment, are genuinely analytics outputs (DS-INV, DS-CUST) that don't exist until Phases 5 and
  7. This phase adds the schema columns/relations needed to display them later
  (`unit_risk`/`lead_scores` tables are analytics tables per DAT-003 and are NOT created here -
  they arrive with their owning phase) and the UI renders "-" / "not yet scored" placeholders
  where a later phase's analytics haven't run yet.
- FR-034 (bulk lead reassignment, P2) and FR-025 (CSV import dry-run, P1) remain backlogged per
  `docs/backlog.md`, unchanged from the existing entries.
