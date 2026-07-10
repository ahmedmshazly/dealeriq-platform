"""GET/POST /branches (FR-020 — branches are a supporting lookup for inventory)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from dealeriq_api.auth.dependencies import require_permission
from dealeriq_api.core.db import get_db
from dealeriq_api.domain.inventory_service import create_branch, list_branches
from dealeriq_api.domain.models.rbac import User
from dealeriq_api.schemas.inventory import BranchCreateRequest, BranchResponse

router = APIRouter(prefix="/api/v1/branches", tags=["branches"])


@router.get("", response_model=list[BranchResponse])
def list_branches_route(
    _current_user: User = Depends(require_permission("inventory:view")),
    db: Session = Depends(get_db),
) -> list[BranchResponse]:
    return [BranchResponse(id=b.id, name=b.name, city=b.city) for b in list_branches(db)]


@router.post("", response_model=BranchResponse, status_code=201)
def create_branch_route(
    body: BranchCreateRequest,
    _request: Request,
    _current_user: User = Depends(require_permission("inventory:manage")),
    db: Session = Depends(get_db),
) -> BranchResponse:
    branch = create_branch(db, name=body.name, city=body.city)
    return BranchResponse(id=branch.id, name=branch.name, city=branch.city)
