"""Customers, with a server-side dedup warning on matching phone/email (FR-030) — creation is
never blocked, only flagged, since a real duplicate might legitimately be a different person at
the same address/shared line."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from dealeriq_api.domain.models.customer import Customer
from dealeriq_api.domain.services.audit import write_audit_row


def find_possible_duplicates(
    db: Session, *, phone: str | None, email: str | None
) -> list[Customer]:
    if not phone and not email:
        return []
    conditions = []
    if phone:
        conditions.append(Customer.phone == phone)
    if email:
        conditions.append(Customer.email == email)
    return list(db.execute(select(Customer).where(or_(*conditions))).scalars().all())


def create_customer(
    db: Session,
    *,
    actor_id: uuid.UUID,
    name: str,
    phone: str | None,
    email: str | None,
    city: str | None,
    source_channel: str | None,
    ip: str | None,
) -> tuple[Customer, list[Customer]]:
    duplicates = find_possible_duplicates(db, phone=phone, email=email)

    customer = Customer(
        name=name, phone=phone, email=email, city=city, source_channel=source_channel
    )
    db.add(customer)
    db.flush()
    write_audit_row(
        db,
        actor_id=actor_id,
        action="customer.created",
        entity_type="customer",
        entity_id=str(customer.id),
        after={"name": name, "phone": phone, "email": email},
        ip=ip,
    )
    db.commit()
    return customer, duplicates


def list_customers(db: Session, *, limit: int, offset: int) -> tuple[list[Customer], int]:
    total = db.execute(select(func.count()).select_from(Customer)).scalar_one()
    rows = (
        db.execute(select(Customer).order_by(Customer.name).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return list(rows), total
