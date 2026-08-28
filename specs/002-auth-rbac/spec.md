# Feature Specification: Auth & RBAC

**Feature Branch**: `002-auth-rbac`

**Created**: 2026-07-10

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 1 - "FR-001..013, SEC/NFR-001/002, audit basics
FR-080"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign in and stay signed in safely (Priority: P1)

As any user, I sign in with email + password and get a working session that doesn't expose my
credentials, expires my access quickly, but doesn't force me to re-enter my password every 15
minutes.

**Why this priority**: Nothing else in the product is reachable without this.

**Independent Test**: Log in via `POST /auth/login`; use the returned access token to call a
protected endpoint; let it expire; call `POST /auth/refresh` (using the httpOnly cookie) and
confirm a new access token works.

**Acceptance Scenarios**:

1. **Given** a valid email/password for an active user, **When** `POST /auth/login`, **Then** the
   response includes a JWT access token (≤15 min expiry) and sets a rotating refresh token as an
   httpOnly, SameSite=Strict cookie (≤7 day expiry) (FR-001).
2. **Given** a password hash stored for a user, **When** inspecting the database or any log,
   **Then** the plaintext password never appears anywhere and the hash is Argon2id with
   memory≥64MiB/iterations≥3 (FR-002, ADR-009).
3. **Given** a valid refresh token cookie, **When** `POST /auth/refresh`, **Then** a new access
   token and a rotated refresh token are issued, and the old refresh token is rejected if reused
   (ADR-019).
4. **Given** a logged-in user, **When** `POST /auth/logout`, **Then** that session's refresh
   token is revoked; **When** `POST /auth/logout-all`, **Then** every refresh token for that
   user is revoked (FR-003).

---

### User Story 2 - Every endpoint enforces its own permission (Priority: P1)

As the system, I deny access by default: every endpoint declares the permission(s) it requires,
and a request without them gets a 403 with a machine-readable error code - regardless of what
the frontend does or doesn't show.

**Why this priority**: This is the security boundary the entire RBAC principle depends on
(constitution Principle III).

**Independent Test**: Call an admin-only endpoint (e.g., `POST /users`) as a Sales-role user;
confirm 403 with `error.code == "forbidden"`.

**Acceptance Scenarios**:

1. **Given** an authenticated Sales user, **When** they call `POST /api/v1/users`, **Then** the
   response is 403 with a structured error envelope (FR-010, FR-011).
2. **Given** an authenticated Admin, **When** they call the same endpoint, **Then** it succeeds
   (proving the check is role-driven, not a blanket lockout).
3. **Given** the permission matrix is stored in the database and seeded by migration, **When**
   `GET /api/v1/permissions/matrix` is called by an Admin, **Then** it returns every role's
   granted permissions (FR-013).

---

### User Story 3 - Admins manage accounts; the audit trail records what happened (Priority: P2)

As an Admin, I create/deactivate/reactivate accounts and assign exactly one role each (no
self-registration in v1.0); every security-relevant action is recorded in an append-only audit
log I can browse.

**Why this priority**: Required for the exit demo ("log in as each role, prove a 403, audit rows
visible") but depends on User Stories 1-2 existing first.

**Independent Test**: Create a user as Admin; deactivate them; confirm two audit_log rows exist
(`user.created`, `user.deactivated`) with actor, before/after, timestamp, IP.

**Acceptance Scenarios**:

1. **Given** an Admin, **When** they `POST /api/v1/users` with an email/role, **Then** a new
   inactive-until-first-login user is created with `must_change_password=true` (FR-004, FR-006)
   and an audit row is written (FR-080).
2. **Given** 5 consecutive failed login attempts for one user within 15 minutes, **When** a 6th
   attempt is made, **Then** the account is locked for 15 minutes or until an Admin unlocks it
   (FR-005).
3. **Given** an Admin, **When** they call `GET /api/v1/audit-log`, **Then** they can filter by
   actor/action/entity/date range with pagination (FR-081 - folded into this phase; see plan.md
   for why FR-081 has no explicit phase assignment in the SRS and the rationale for including it
   here rather than deferring).

### Edge Cases

- What happens when a refresh token is presented twice (theft/replay)? → the entire token family
  is revoked and the user must re-authenticate (ADR-019).
- What happens when an Admin deactivates their own account? → allowed but the acting session is
  not force-terminated mid-request; their next refresh attempt fails.
- What happens when a locked-out user has the correct password? → still rejected until the
  lockout window elapses or an Admin unlocks the account.
- What happens when a Sales user tries to view another user's account details? → `users:manage`
  is Admin-only; Sales has no `users:*` permission at all, so 403.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System SHALL issue a JWT access token (≤15 min) and rotating refresh token
  (≤7 days, httpOnly, SameSite=Strict cookie) on successful email+password login.
- **FR-002**: Passwords SHALL be hashed with Argon2id (memory≥64MiB, iterations≥3); never logged
  or returned.
- **FR-003**: System SHALL support logout (revoke current refresh token) and logout-all (revoke
  every refresh token for the user).
- **FR-004**: Admins SHALL create, deactivate, and reactivate accounts, assigning exactly one
  role per user. Self-registration is disabled.
- **FR-005**: System SHALL lock an account after 5 consecutive failed logins within 15 minutes;
  unlock after 15 minutes or by admin action.
- **FR-006**: System SHALL support a forced password-change flag on first login for admin-created
  accounts.
- **FR-010**: Every endpoint SHALL declare required permissions; lacking them returns 403 with a
  machine-readable error code.
- **FR-011**: Permission checks SHALL be enforced only in the API layer.
- **FR-012**: Sales users SHALL only edit resources they own once owned resources exist (Phase
  2); the ownership-check mechanism is implemented and unit-tested generically in this phase.
- **FR-013**: The permission matrix SHALL be DB-stored, migration-seeded, and viewable by Admins.
- **FR-080**: An append-only audit log SHALL record actor, action, entity, before/after, IP, and
  timestamp for auth events, role changes, and approvals (approvals arrive Phase 2; auth/role
  events are this phase's scope).
- **FR-081** *(folded in - see plan.md)*: Admins SHALL browse/filter/export the audit log.

### Key Entities

- **User**: email (unique), password_hash, role, is_active, must_change_password,
  failed_login_count, locked_until.
- **Role**: Admin / Manager / Sales / Analyst.
- **Permission**: a granular string key (e.g., `users:manage`) grouped into roles via
  **RolePermission**.
- **RefreshToken**: token_hash (never the raw token), user, expiry, revoked_at, replaced_by
  (rotation chain).
- **AuditLog**: append-only; actor, action, entity_type, entity_id, before/after JSON, IP,
  timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user of each of the 4 roles can log in and reach a role-appropriate authenticated
  page.
- **SC-002**: A 403 with `error.code == "forbidden"` is produced for at least one endpoint per
  non-Admin role attempting an Admin-only action.
- **SC-003**: Audit rows are visible (via `GET /api/v1/audit-log`) for login, user creation, and
  role/deactivation changes.
- **SC-004**: `make ci` stays green; new code carries ≥80% coverage on `auth/`, `domain/`
  (users/roles/permissions/audit), consistent with the constitution's testing bar.

## Assumptions

- Phase 2's domain resources (orders, leads) don't exist yet, so FR-012's ownership check is
  implemented and tested as a reusable mechanism now, demonstrated end-to-end once those
  resources exist.
- A first Admin account must exist on a fresh seed for anyone to log in at all (self-registration
  is disabled per FR-004) - seeded via `make seed` from an env-configurable default, documented
  in `.env.example`, forced to change password on first login.
