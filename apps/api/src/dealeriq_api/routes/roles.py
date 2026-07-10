"""GET /roles (FR-013)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dealeriq_api.auth.admin_service import list_roles
from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.auth.schemas import RoleResponse
from dealeriq_api.core.db import get_db
from dealeriq_api.domain.models.rbac import User

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


@router.get("", response_model=list[RoleResponse])
def list_roles_route(
    _current_user: User = Depends(require_permission("users:view")),
    db: Session = Depends(get_db),
) -> list[RoleResponse]:
    roles = list_roles(db)
    return [RoleResponse(id=r.id, key=r.key, name=r.name) for r in roles]
