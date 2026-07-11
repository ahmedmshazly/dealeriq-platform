"""Seed-time orchestrator (T010, GEN-001..006): runs the statistical generator
(`dealeriq_analytics.generator`) and bulk-inserts the resulting world into Postgres via
SQLAlchemy Core, then writes GEN-006's ground-truth JSON artifacts to
`infra/seed/ground_truth/`.

Bypasses the API/service layer deliberately (spec.md's Assumptions): this is a one-time,
seed-time bulk load, not a runtime analytics job — DAT-003's transactional/analytics separation
is about protecting live data from *runtime* jobs, not about how the initial dataset is loaded.
Every row still matches the exact schema/constraints those tables enforce.

Run directly: `uv run python infra/seed/generate.py` from the repo root (wired to `make seed`).
"""

import dataclasses
import datetime as dt
import json
import pathlib
import uuid
from dataclasses import asdict
from typing import cast

import numpy as np
from sqlalchemy import Table, insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase

from dealeriq_analytics.generator.anomalies import (
    AnomalyRecord,
    find_near_miss_points,
    inject_demand_shocks,
)
from dealeriq_analytics.generator.config import GeneratorConfig
from dealeriq_analytics.generator.demand import GeneratedDemand, ModelDef, generate_demand
from dealeriq_analytics.generator.leads import (
    CHANNELS,
    SimulatedLead,
    ground_truth_coefficients,
    simulate_leads,
)
from dealeriq_analytics.sbc import DegenerateSeriesError, classify_with_stats
from dealeriq_api.auth.passwords import hash_password
from dealeriq_api.core.db import engine
from dealeriq_api.domain.lead_state_machine import ALLOWED_TRANSITIONS
from dealeriq_api.domain.models import (
    Branch,
    Customer,
    Lead,
    LeadEvent,
    LeadStatus,
    MovementType,
    Order,
    OrderEvent,
    OrderStatus,
    PaymentType,
    Role,
    StockMovement,
    UnitStatus,
    User,
    VehicleModel,
    VehicleUnit,
)

GROUND_TRUTH_DIR = pathlib.Path(__file__).parent / "ground_truth"

# Week 155 (the last week of the 156-week history) starts on this Monday; earlier weeks count
# backward from here. Fixed (not "today - 156 weeks") so re-running the generator on a different
# calendar day still produces byte-identical dates (GEN-001, SC-005).
REFERENCE_LAST_WEEK_START = dt.date(2026, 7, 6)

DISCOUNT_APPROVAL_THRESHOLD = 0.05  # mirrors Settings.order_approval_discount_threshold
REPEAT_CUSTOMER_PROBABILITY = 0.70  # plan.md: "~70% chance of an existing customer"

N_LEADS = 6000
N_SHOCKS = 20
N_NEAR_MISS = 5

CURRENT_INVENTORY_WEEKS_OF_SUPPLY = 3
CURRENT_INVENTORY_MAX_UNITS_PER_SERIES = 6
CURRENT_INVENTORY_ACQUISITION_WINDOW_DAYS = 150
"""~150 days back from "today" (REFERENCE_LAST_WEEK_START + 6) deliberately spans past the
default 90-day aging threshold (DS-INV-003), so the seeded current-inventory population includes
both fresh and genuinely aging units rather than only fresh ones."""

FIRST_NAMES = [
    "James",
    "Mary",
    "Robert",
    "Patricia",
    "John",
    "Jennifer",
    "Michael",
    "Linda",
    "David",
    "Elizabeth",
    "William",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Sarah",
    "Charles",
    "Karen",
    "Christopher",
    "Nancy",
    "Daniel",
    "Lisa",
    "Matthew",
    "Betty",
    "Anthony",
    "Margaret",
    "Mark",
    "Sandra",
    "Donald",
    "Ashley",
    "Steven",
    "Kimberly",
    "Andrew",
    "Emily",
    "Paul",
    "Donna",
    "Joshua",
    "Michelle",
    "Kenneth",
    "Carol",
    "Kevin",
    "Amanda",
    "Brian",
    "Melissa",
    "George",
    "Deborah",
    "Edward",
    "Stephanie",
]
LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
    "Harris",
    "Sanchez",
    "Clark",
    "Ramirez",
    "Lewis",
    "Robinson",
    "Walker",
    "Young",
    "Allen",
    "King",
    "Wright",
    "Scott",
    "Torres",
    "Nguyen",
    "Hill",
    "Flores",
    "Green",
    "Adams",
    "Nelson",
    "Baker",
    "Hall",
    "Rivera",
    "Campbell",
    "Mitchell",
    "Carter",
    "Roberts",
]
CUSTOMER_CITIES = [
    "Metropolis",
    "Gateway City",
    "Riverside",
    "Lakeview",
    "Fairview",
    "Brookfield",
    "Ashland",
]
SALES_REP_COUNT = 8
MANAGER_COUNT = 2
SEED_USER_PASSWORD = "SeedUser123!"


def _table(model: type[DeclarativeBase]) -> Table:
    return cast(Table, model.__table__)


def _new_id() -> uuid.UUID:
    return uuid.uuid4()


def _week_start(week_index: int, n_weeks: int) -> dt.date:
    weeks_before_last = (n_weeks - 1) - week_index
    return REFERENCE_LAST_WEEK_START - dt.timedelta(weeks=weeks_before_last)


def _as_datetime(day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=dt.UTC)


class CustomerPool:
    """Organically-growing customer list shared by both order and lead realization, so repeat
    purchases and repeat lead contacts land on the same people (plan.md: "~70% chance of an
    existing customer making a repeat purchase, ~30% a new one"). A newly-created customer's
    `source_channel` is set to the acquiring lead's simulated channel when one is given — without
    this, Customer.source_channel would be statistically independent of Lead.status in the
    database, even though `dealeriq_analytics.generator.leads` deliberately makes channel a real
    driver of the won/lost outcome (GEN-003's whole point is a *recoverable* channel signal)."""

    def __init__(self, rng: np.random.Generator) -> None:
        self._rng = rng
        self.rows: list[dict[str, object]] = []
        self.ids: list[uuid.UUID] = []

    def pick_or_create(self, at: dt.datetime, preferred_channel: str | None = None) -> uuid.UUID:
        if self.ids and self._rng.uniform() < REPEAT_CUSTOMER_PROBABILITY:
            return self.ids[int(self._rng.integers(0, len(self.ids)))]
        return self._create(at, preferred_channel)

    def _create(self, at: dt.datetime, preferred_channel: str | None) -> uuid.UUID:
        first = FIRST_NAMES[int(self._rng.integers(0, len(FIRST_NAMES)))]
        last = LAST_NAMES[int(self._rng.integers(0, len(LAST_NAMES)))]
        city = CUSTOMER_CITIES[int(self._rng.integers(0, len(CUSTOMER_CITIES)))]
        channel = preferred_channel or CHANNELS[int(self._rng.integers(0, len(CHANNELS)))]
        n = len(self.ids)
        customer_id = _new_id()
        self.rows.append(
            {
                "id": customer_id,
                "name": f"{first} {last}",
                "phone": f"555-{100000 + n:06d}",
                "email": f"{first.lower()}.{last.lower()}{n}@example.com",
                "city": city,
                "source_channel": channel,
                "created_at": at,
                "updated_at": at,
            }
        )
        self.ids.append(customer_id)
        return customer_id


def _build_branches(config: GeneratorConfig) -> list[dict[str, object]]:
    now = _as_datetime(REFERENCE_LAST_WEEK_START, 8)
    rows = []
    for name, city, _branch_effect in config.branches:
        rows.append(
            {
                "id": _new_id(),
                "name": name,
                "city": city,
                "created_at": now,
                "updated_at": now,
            }
        )
    return rows


def _build_vehicle_models(demand: GeneratedDemand) -> list[dict[str, object]]:
    now = _as_datetime(REFERENCE_LAST_WEEK_START, 8)
    rows = []
    for model_def in demand.model_defs:
        rows.append(
            {
                "id": _new_id(),
                "make": model_def.make,
                "model": model_def.model,
                "trim": None,
                "segment": model_def.segment_key,
                "list_price": round(model_def.list_price, 2),
                "created_at": now,
                "updated_at": now,
            }
        )
    return rows


def _build_users(conn: Connection) -> list[dict[str, object]]:
    now = _as_datetime(REFERENCE_LAST_WEEK_START, 8)
    role_ids: dict[str, uuid.UUID] = {
        row.key: row.id for row in conn.execute(select(Role.key, Role.id))
    }
    password_hash = hash_password(SEED_USER_PASSWORD)
    rows = []
    for i in range(SALES_REP_COUNT):
        rows.append(
            {
                "id": _new_id(),
                "email": f"sales{i + 1}@dealeriq.dev",
                "password_hash": password_hash,
                "role_id": role_ids["sales"],
                "is_active": True,
                "must_change_password": False,
                "failed_login_count": 0,
                "last_failed_login_at": None,
                "locked_until": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    for i in range(MANAGER_COUNT):
        rows.append(
            {
                "id": _new_id(),
                "email": f"manager{i + 1}@dealeriq.dev",
                "password_hash": password_hash,
                "role_id": role_ids["manager"],
                "is_active": True,
                "must_change_password": False,
                "failed_login_count": 0,
                "last_failed_login_at": None,
                "locked_until": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    rows.append(
        {
            "id": _new_id(),
            "email": "analyst1@dealeriq.dev",
            "password_hash": password_hash,
            "role_id": role_ids["analyst"],
            "is_active": True,
            "must_change_password": False,
            "failed_login_count": 0,
            "last_failed_login_at": None,
            "locked_until": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    return rows


def _realize_orders(
    mutated_series: dict[tuple[str, str], np.ndarray],
    branch_ids: dict[str, uuid.UUID],
    model_ids: dict[str, uuid.UUID],
    model_by_key: dict[str, ModelDef],
    sales_user_ids: list[uuid.UUID],
    manager_user_ids: list[uuid.UUID],
    customer_pool: CustomerPool,
    rng: np.random.Generator,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Every unit of demand realized is one delivered order (plan.md's "Order/inventory
    realization"): a fresh vehicle unit, a receipt + sale stock movement, an order, and its
    submit/[approve]/deliver event trail — all backdated within that (model, branch, week)."""
    n_weeks = 156

    sale_events: list[tuple[int, str, str]] = []
    for (model_key, branch_name), series in mutated_series.items():
        for t, count in enumerate(series):
            sale_events.extend([(t, model_key, branch_name)] * int(count))
    sale_events.sort(key=lambda e: e[0])

    units: list[dict[str, object]] = []
    movements: list[dict[str, object]] = []
    orders: list[dict[str, object]] = []
    order_events: list[dict[str, object]] = []

    for t, model_key, branch_name in sale_events:
        week_start = _week_start(t, n_weeks)
        model_def = model_by_key[model_key]
        list_price = float(model_def.list_price)

        acquisition_day = week_start + dt.timedelta(days=int(rng.integers(0, 3)))
        submit_day = acquisition_day + dt.timedelta(days=int(rng.integers(0, 2)))
        approval_extra_days = int(rng.integers(0, 2))
        deliver_day = submit_day + dt.timedelta(days=approval_extra_days + int(rng.integers(1, 3)))

        acquisition_cost = round(list_price * float(rng.uniform(0.75, 0.85)), 2)
        discount_fraction = float(min(rng.exponential(0.03), 0.25))
        discount = round(list_price * discount_fraction, 2)
        negotiated_price = round(list_price - discount, 2)
        payment_type = PaymentType.FINANCE if rng.uniform() < 0.6 else PaymentType.CASH

        unit_id = _new_id()
        vin = f"DLQ{len(units):014d}"
        units.append(
            {
                "id": unit_id,
                "vin": vin,
                "model_id": model_ids[model_key],
                "branch_id": branch_ids[branch_name],
                "status": UnitStatus.SOLD,
                "acquisition_date": acquisition_day,
                "acquisition_cost": acquisition_cost,
                "created_at": _as_datetime(acquisition_day, 9),
                "updated_at": _as_datetime(deliver_day, 17),
            }
        )

        manager_id = manager_user_ids[int(rng.integers(0, len(manager_user_ids)))]
        salesperson_id = sales_user_ids[int(rng.integers(0, len(sales_user_ids)))]

        movements.append(
            {
                "id": _new_id(),
                "unit_id": unit_id,
                "type": MovementType.RECEIPT,
                "from_branch_id": None,
                "to_branch_id": branch_ids[branch_name],
                "actor_id": manager_id,
                "reason": "Seed generator: inbound stock receipt.",
                "occurred_at": _as_datetime(acquisition_day, 9),
            }
        )
        movements.append(
            {
                "id": _new_id(),
                "unit_id": unit_id,
                "type": MovementType.SALE,
                "from_branch_id": branch_ids[branch_name],
                "to_branch_id": None,
                "actor_id": salesperson_id,
                "reason": "Seed generator: unit sold and delivered.",
                "occurred_at": _as_datetime(deliver_day, 17),
            }
        )

        customer_id = customer_pool.pick_or_create(_as_datetime(acquisition_day, 9))

        order_id = _new_id()
        orders.append(
            {
                "id": order_id,
                "customer_id": customer_id,
                "unit_id": unit_id,
                "salesperson_id": salesperson_id,
                "negotiated_price": negotiated_price,
                "discount": discount,
                "payment_type": payment_type,
                "status": OrderStatus.DELIVERED,
                "created_at": _as_datetime(acquisition_day, 10),
                "updated_at": _as_datetime(deliver_day, 17),
                # Not a real orders-table column — used to group by model for pricing-error
                # injection (GEN-004) and stripped before the bulk insert.
                "_model_key": model_key,
            }
        )

        needs_approval = discount_fraction > DISCOUNT_APPROVAL_THRESHOLD
        submit_to = OrderStatus.PENDING_APPROVAL if needs_approval else OrderStatus.APPROVED
        order_events.append(
            {
                "id": _new_id(),
                "order_id": order_id,
                "from_status": OrderStatus.DRAFT.value,
                "to_status": submit_to.value,
                "actor_id": salesperson_id,
                "reason": None,
                "at": _as_datetime(submit_day, 11),
            }
        )
        approve_day = submit_day + dt.timedelta(days=approval_extra_days)
        if needs_approval:
            order_events.append(
                {
                    "id": _new_id(),
                    "order_id": order_id,
                    "from_status": OrderStatus.PENDING_APPROVAL.value,
                    "to_status": OrderStatus.APPROVED.value,
                    "actor_id": manager_id,
                    "reason": None,
                    "at": _as_datetime(approve_day, 14),
                }
            )
        order_events.append(
            {
                "id": _new_id(),
                "order_id": order_id,
                "from_status": OrderStatus.APPROVED.value,
                "to_status": OrderStatus.DELIVERED.value,
                "actor_id": salesperson_id,
                "reason": None,
                "at": _as_datetime(deliver_day, 17),
            }
        )

    return units, movements, orders, order_events


def _realize_current_inventory(
    mutated_series: dict[tuple[str, str], np.ndarray],
    branch_ids: dict[str, uuid.UUID],
    model_ids: dict[str, uuid.UUID],
    model_by_key: dict[str, ModelDef],
    manager_user_ids: list[uuid.UUID],
    rng: np.random.Generator,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """`_realize_orders` only ever creates units tied to an already-delivered order — a real
    dealership also carries current, not-yet-sold inventory on the lot, which Phase 5's
    DS-INV-003/004 (days-on-lot, survival-curve pricing review) needs to have anything to
    compute over. Sizes each series' current stock at a standard "weeks of supply" heuristic
    (`CURRENT_INVENTORY_WEEKS_OF_SUPPLY` * that series' own mean weekly demand), so higher-
    velocity series realistically carry more lot inventory than slow ones. Acquisition dates are
    spread over `CURRENT_INVENTORY_ACQUISITION_WINDOW_DAYS` days before "today" (deliberately
    spanning past DS-INV-003's default 90-day aging threshold) so the seeded population includes
    both fresh and genuinely aging units, not just fresh ones."""
    today = REFERENCE_LAST_WEEK_START + dt.timedelta(days=6)
    units: list[dict[str, object]] = []
    movements: list[dict[str, object]] = []

    for (model_key, branch_name), series in mutated_series.items():
        mean_weekly_demand = float(np.mean(series))
        if mean_weekly_demand <= 0:
            continue
        n_units = min(
            CURRENT_INVENTORY_MAX_UNITS_PER_SERIES,
            max(1, round(mean_weekly_demand * CURRENT_INVENTORY_WEEKS_OF_SUPPLY)),
        )
        model_def = model_by_key[model_key]
        list_price = float(model_def.list_price)

        for _ in range(n_units):
            days_back = int(rng.integers(0, CURRENT_INVENTORY_ACQUISITION_WINDOW_DAYS))
            acquisition_day = today - dt.timedelta(days=days_back)
            acquisition_cost = round(list_price * float(rng.uniform(0.75, 0.85)), 2)
            manager_id = manager_user_ids[int(rng.integers(0, len(manager_user_ids)))]

            unit_id = _new_id()
            units.append(
                {
                    "id": unit_id,
                    "vin": f"DLQ{len(units) + 900_000:014d}",
                    "model_id": model_ids[model_key],
                    "branch_id": branch_ids[branch_name],
                    "status": UnitStatus.IN_STOCK,
                    "acquisition_date": acquisition_day,
                    "acquisition_cost": acquisition_cost,
                    "created_at": _as_datetime(acquisition_day, 9),
                    "updated_at": _as_datetime(acquisition_day, 9),
                }
            )
            movements.append(
                {
                    "id": _new_id(),
                    "unit_id": unit_id,
                    "type": MovementType.RECEIPT,
                    "from_branch_id": None,
                    "to_branch_id": branch_ids[branch_name],
                    "actor_id": manager_id,
                    "reason": "Seed generator: current lot inventory, not yet sold.",
                    "occurred_at": _as_datetime(acquisition_day, 9),
                }
            )

    return units, movements


PRICING_ERROR_K = 5.0  # DS-ANO-003: k_inject=5 vs. the detector's default k=3
N_PRICING_ERRORS = 15
MIN_ORDERS_FOR_PRICING_STATS = 5


@dataclasses.dataclass(frozen=True)
class PricingErrorRecord:
    order_id: str
    model_key: str
    list_price: float
    historical_discount_fraction_mean: float
    historical_discount_fraction_std: float
    k_inject: float
    original_negotiated_price: float
    injected_negotiated_price: float


def _inject_pricing_errors(
    orders: list[dict[str, object]],
    model_by_key: dict[str, ModelDef],
    rng: np.random.Generator,
    n_errors: int = N_PRICING_ERRORS,
) -> list[PricingErrorRecord]:
    """GEN-004's other half: forces `negotiated_price` on a handful of orders below
    `list_price - k*sigma(historical discount fractions for that model)`, k=5 vs. the real
    detector's default k=3 (DS-ANO-003) — comfortably past threshold, not a coin-flip."""
    orders_by_model: dict[str, list[int]] = {}
    for i, order in enumerate(orders):
        orders_by_model.setdefault(cast(str, order["_model_key"]), []).append(i)

    candidates = [
        model_key
        for model_key, indices in orders_by_model.items()
        if len(indices) >= MIN_ORDERS_FOR_PRICING_STATS
    ]
    rng.shuffle(candidates)

    records: list[PricingErrorRecord] = []
    used_orders: set[int] = set()
    for model_key in candidates:
        if len(records) >= n_errors:
            break
        list_price = float(model_by_key[model_key].list_price)
        indices = orders_by_model[model_key]
        fractions = [1.0 - cast(float, orders[i]["negotiated_price"]) / list_price for i in indices]
        mean = float(np.mean(fractions))
        std = float(np.std(fractions))
        if std <= 0:
            continue

        available = [i for i in indices if i not in used_orders]
        if not available:
            continue
        idx = available[int(rng.integers(0, len(available)))]
        order = orders[idx]

        injected_fraction = min(mean + PRICING_ERROR_K * std, 0.9)
        original_price = cast(float, order["negotiated_price"])
        injected_price = round(list_price * (1.0 - injected_fraction), 2)

        order["negotiated_price"] = injected_price
        order["discount"] = round(list_price - injected_price, 2)
        used_orders.add(idx)

        records.append(
            PricingErrorRecord(
                order_id=str(order["id"]),
                model_key=model_key,
                list_price=list_price,
                historical_discount_fraction_mean=round(mean, 4),
                historical_discount_fraction_std=round(std, 4),
                k_inject=PRICING_ERROR_K,
                original_negotiated_price=original_price,
                injected_negotiated_price=injected_price,
            )
        )

    return records


def _walk_lead_funnel(won: bool, rng: np.random.Generator) -> list[tuple[LeadStatus, LeadStatus]]:
    """Walks ALLOWED_TRANSITIONS from `new` to a terminal state consistent with `won`, so the
    seeded event trail is a real, legal path through the same state machine the API enforces.
    Filters WON out of the option set for lost-destined leads (and vice versa) at every step —
    `negotiating`'s only two exits are `won`/`lost`, so without this a lost-destined lead could
    randomly resolve to `won` there, contradicting the ground-truth `won` flag it was given."""
    path: list[tuple[LeadStatus, LeadStatus]] = []
    current = LeadStatus.NEW
    while current not in (LeadStatus.WON, LeadStatus.LOST):
        options = sorted(ALLOWED_TRANSITIONS[current], key=lambda s: s.value)
        if won:
            options = [s for s in options if s != LeadStatus.LOST] or options
        else:
            options = [s for s in options if s != LeadStatus.WON] or options
            if LeadStatus.LOST in options and rng.uniform() < 0.4:
                path.append((current, LeadStatus.LOST))
                current = LeadStatus.LOST
                break
        next_status = (
            options[int(rng.integers(0, len(options)))] if len(options) > 1 else options[0]
        )
        path.append((current, next_status))
        current = next_status
    return path


def _realize_leads(
    leads: list[SimulatedLead],
    model_defs_by_segment: dict[str, list[str]],
    model_ids: dict[str, uuid.UUID],
    sales_user_ids: list[uuid.UUID],
    customer_pool: CustomerPool,
    rng: np.random.Generator,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Every simulated lead has a resolved (`won`/`lost`) ground-truth outcome (GEN-003's logit
    simulation always terminates), but that doesn't mean every lead has *finished its real
    calendar-time journey* to that outcome by "today" (`REFERENCE_LAST_WEEK_START` + 6 days, the
    same reference `_realize_current_inventory` uses). A lead created only a few real days ago
    can't have already walked its full funnel if that funnel's own gap-day spacing implies more
    elapsed time than has actually passed — so its walk is truncated to however many steps would
    plausibly have happened by today, leaving it at a genuinely open, non-terminal status. Leads
    created long enough ago always finish their walk unchanged. Without this, every lead in the
    seeded database resolves to won/lost and Phase 7's lead-scoring/idle-alert features would
    have no open leads to ever operate on."""
    n_weeks = 156
    today = REFERENCE_LAST_WEEK_START + dt.timedelta(days=6)
    lead_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []

    for lead in leads:
        created_day = _week_start(lead.creation_week, n_weeks) + dt.timedelta(
            days=int(rng.integers(0, 7))
        )
        created_at = _as_datetime(created_day, int(rng.integers(8, 17)))
        customer_id = customer_pool.pick_or_create(created_at, preferred_channel=lead.channel)
        candidates = model_defs_by_segment.get(lead.segment) or next(
            iter(model_defs_by_segment.values())
        )
        model_key = candidates[int(rng.integers(0, len(candidates)))]
        owner_id = sales_user_ids[int(rng.integers(0, len(sales_user_ids)))]

        full_path = _walk_lead_funnel(lead.won, rng)
        n_events = max(len(full_path), 1)
        gap_days = max(lead.days_since_creation // n_events, 1)

        days_elapsed = max((today - created_day).days, 0)
        steps_completed = min(len(full_path), days_elapsed // gap_days)
        path = full_path[:steps_completed]
        final_status = path[-1][1] if path else LeadStatus.NEW

        lead_id = _new_id()
        last_activity_at = created_at
        for i, (from_status, to_status) in enumerate(path):
            event_at = created_at + dt.timedelta(days=gap_days * (i + 1))
            event_rows.append(
                {
                    "id": _new_id(),
                    "lead_id": lead_id,
                    "type": f"status_change:{from_status.value}->{to_status.value}",
                    "notes": None,
                    "actor_id": owner_id,
                    "at": event_at,
                }
            )
            last_activity_at = event_at

        lead_rows.append(
            {
                "id": lead_id,
                "customer_id": customer_id,
                "model_id": model_ids[model_key],
                "budget_band": lead.budget_band,
                "status": final_status,
                "owner_id": owner_id,
                "last_activity_at": last_activity_at,
                "created_at": created_at,
                "updated_at": last_activity_at,
            }
        )

    return lead_rows, event_rows


def _write_ground_truth(
    demand: GeneratedDemand,
    config: GeneratorConfig,
    shock_records: list[AnomalyRecord],
    near_miss_records: list[AnomalyRecord],
    pricing_error_records: list[PricingErrorRecord],
    n_leads: int,
) -> None:
    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)

    generator_config = {
        "seed": config.seed,
        "n_weeks": config.n_weeks,
        "branches": [
            {"name": name, "city": city, "branch_effect": effect}
            for name, city, effect in config.branches
        ],
        "segments": [
            {
                "key": s.key,
                "display_name": s.display_name,
                "target_sbc_class": s.target_sbc_class,
                "mu0_range": list(s.mu0_range),
                "dispersion_range": list(s.dispersion_range),
                "n_models": s.n_models,
            }
            for s in config.segments
        ],
        "n_leads": n_leads,
    }
    (GROUND_TRUTH_DIR / "generator_config.json").write_text(json.dumps(generator_config, indent=2))

    series_params = [
        {
            "model_key": p.model_key,
            "branch_name": p.branch_name,
            "beta0": p.beta0,
            "beta_trend": p.beta_trend,
            "fourier": [list(pair) for pair in p.fourier],
            "branch_effect": p.branch_effect,
            "dispersion": p.dispersion,
            "beta_promo": p.beta_promo,
            "promo_weeks": list(p.promo_weeks),
            "target_sbc_class": p.target_sbc_class,
        }
        for p in demand.series_params
    ]
    (GROUND_TRUTH_DIR / "series_params.json").write_text(json.dumps(series_params, indent=2))

    coeffs = ground_truth_coefficients()
    (GROUND_TRUTH_DIR / "lead_coefficients.json").write_text(json.dumps(asdict(coeffs), indent=2))

    anomalies = [asdict(r) for r in shock_records] + [asdict(r) for r in near_miss_records]
    (GROUND_TRUTH_DIR / "anomalies.json").write_text(json.dumps(anomalies, indent=2))

    pricing_errors = [asdict(r) for r in pricing_error_records]
    (GROUND_TRUTH_DIR / "pricing_errors.json").write_text(json.dumps(pricing_errors, indent=2))


def _sbc_class_counts(series_by_key: dict[tuple[str, str], np.ndarray]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for series in series_by_key.values():
        try:
            sbc_class, _adi, _cv2 = classify_with_stats(series.astype(np.float64))
            counts[sbc_class.value] = counts.get(sbc_class.value, 0) + 1
        except DegenerateSeriesError:
            counts["degenerate"] = counts.get("degenerate", 0) + 1
    return counts


def main() -> None:
    config = GeneratorConfig()
    master_seq = np.random.SeedSequence(config.seed)
    (
        rng_anomaly,
        rng_near_miss,
        rng_leads,
        rng_realize,
        rng_customers,
        rng_pricing,
        rng_current_inventory,
    ) = (np.random.default_rng(s) for s in master_seq.spawn(7))

    print("Generating demand series...")
    demand = generate_demand(config)
    mutated_series, shock_records = inject_demand_shocks(demand, rng_anomaly, n_shocks=N_SHOCKS)
    near_miss_records = find_near_miss_points(demand, rng_near_miss, n_near_miss=N_NEAR_MISS)
    total_volume = sum(int(s.sum()) for s in mutated_series.values())
    sbc_counts = _sbc_class_counts(mutated_series)
    print(
        f"  {len(demand.model_defs)} models, {len(mutated_series)} series, "
        f"{total_volume} total units, SBC coverage: {sbc_counts}"
    )

    print("Generating lead funnel...")
    leads = simulate_leads(N_LEADS, config.n_weeks, rng_leads)
    won_count = sum(1 for lead in leads if lead.won)
    print(f"  {len(leads)} leads, {won_count} won ({won_count / len(leads):.1%})")

    with engine.begin() as conn:
        print("Inserting branches, vehicle models, users...")
        branch_rows = _build_branches(config)
        conn.execute(insert(_table(Branch)), branch_rows)
        branch_ids: dict[str, uuid.UUID] = {
            cast(str, row["name"]): cast(uuid.UUID, row["id"]) for row in branch_rows
        }

        model_rows = _build_vehicle_models(demand)
        conn.execute(insert(_table(VehicleModel)), model_rows)
        model_ids: dict[str, uuid.UUID] = {
            f"{md.segment_key}:{md.make}:{md.model}": cast(uuid.UUID, row["id"])
            for md, row in zip(demand.model_defs, model_rows, strict=True)
        }
        model_by_key = {f"{md.segment_key}:{md.make}:{md.model}": md for md in demand.model_defs}
        model_defs_by_segment: dict[str, list[str]] = {}
        for key, md in model_by_key.items():
            model_defs_by_segment.setdefault(md.segment_key, []).append(key)

        user_rows = _build_users(conn)
        conn.execute(insert(_table(User)), user_rows)
        sales_user_ids: list[uuid.UUID] = [
            cast(uuid.UUID, row["id"])
            for row in user_rows
            if cast(str, row["email"]).startswith("sales")
        ]
        manager_user_ids: list[uuid.UUID] = [
            cast(uuid.UUID, row["id"])
            for row in user_rows
            if cast(str, row["email"]).startswith("manager")
        ]

        customer_pool = CustomerPool(rng_customers)

        print("Realizing orders from demand series (units, ledger, orders)...")
        units, movements, orders, order_events = _realize_orders(
            mutated_series,
            branch_ids,
            model_ids,
            model_by_key,
            sales_user_ids,
            manager_user_ids,
            customer_pool,
            rng_realize,
        )

        print("Realizing leads...")
        lead_rows, lead_event_rows = _realize_leads(
            leads, model_defs_by_segment, model_ids, sales_user_ids, customer_pool, rng_leads
        )

        print("Realizing current (not-yet-sold) lot inventory...")
        current_inventory_units, current_inventory_movements = _realize_current_inventory(
            mutated_series,
            branch_ids,
            model_ids,
            model_by_key,
            manager_user_ids,
            rng_current_inventory,
        )
        units.extend(current_inventory_units)
        movements.extend(current_inventory_movements)
        print(f"  {len(current_inventory_units)} current-inventory units")

        pricing_error_records = _inject_pricing_errors(orders, model_by_key, rng_pricing)
        print(f"  {len(pricing_error_records)} injected pricing errors")
        for order in orders:
            del order["_model_key"]

        print(f"  {len(customer_pool.rows)} distinct customers")
        conn.execute(insert(_table(Customer)), customer_pool.rows)

        print(f"  {len(units)} vehicle units, {len(movements)} stock movements")
        _bulk_insert(conn, _table(VehicleUnit), units)
        _bulk_insert(conn, _table(StockMovement), movements)

        print(f"  {len(orders)} orders, {len(order_events)} order events")
        _bulk_insert(conn, _table(Order), orders)
        _bulk_insert(conn, _table(OrderEvent), order_events)

        print(f"  {len(lead_rows)} leads, {len(lead_event_rows)} lead events")
        _bulk_insert(conn, _table(Lead), lead_rows)
        _bulk_insert(conn, _table(LeadEvent), lead_event_rows)

    print("Writing ground-truth artifacts...")
    _write_ground_truth(
        demand, config, shock_records, near_miss_records, pricing_error_records, N_LEADS
    )

    print("Done.")


def _bulk_insert(
    conn: Connection, table: Table, rows: list[dict[str, object]], batch_size: int = 5000
) -> None:
    if not rows:
        return
    for i in range(0, len(rows), batch_size):
        conn.execute(insert(table), rows[i : i + batch_size])


if __name__ == "__main__":
    main()
