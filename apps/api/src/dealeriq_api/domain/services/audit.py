"""write_audit_row(): the one path every mutating action goes through to record itself
(constitution Principle IV, FR-080)."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from dealeriq_api.domain.models.audit_log import AuditLog


def write_audit_row(
    session: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before,
        after_json=after,
        ip=ip,
    )
    session.add(row)
    return row
