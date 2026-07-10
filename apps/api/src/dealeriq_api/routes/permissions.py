"""GET /permissions/matrix (FR-013)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dealeriq_api.auth.admin_service import permission_matrix
from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.auth.schemas import PermissionMatrixEntry
from dealeriq_api.core.db import get_db
from dealeriq_api.domain.models.rbac import User

router = APIRouter(prefix="/api/v1/permissions", tags=["permissions"])


@router.get("/matrix", response_model=list[PermissionMatrixEntry])
def permission_matrix_route(
    _current_user: User = Depends(require_permission("permissions:view")),
    db: Session = Depends(get_db),
) -> list[PermissionMatrixEntry]:
    matrix = permission_matrix(db)
    return [
        PermissionMatrixEntry(role_key=role.key, role_name=role.name, permissions=perms)
        for role, perms in matrix
    ]
