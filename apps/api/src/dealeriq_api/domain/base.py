"""SQLAlchemy 2.0 typed declarative base shared by every domain model (ADR-011).

No tables are defined against this yet — that begins in Phase 1 (auth/RBAC) and Phase 2
(core domain). Alembic's autogenerate (ADR-011: draft-then-review policy) targets
`Base.metadata` via alembic/env.py.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
