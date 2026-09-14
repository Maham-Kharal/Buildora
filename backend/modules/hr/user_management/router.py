from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.deps import get_db, require_role
from backend.db.models import User
from backend.modules.hr.user_management.schemas import CreateUserSchema, ResetPasswordSchema, UserResponseSchema
from backend.modules.hr.user_management.service import create_new_user, list_all_users, reset_user_password

router = APIRouter(prefix="/hr/users", tags=["HR - User Account Management"])

@router.post("", response_model=UserResponseSchema)
def create_user(
    payload: CreateUserSchema,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_role(["HR_MANAGER", "ADMIN"]))
):
    """Create new employee user account with assigned role (WORKER, ADMIN, HR_MANAGER)."""
    return create_new_user(db, hr_user.id, payload)

@router.get("", response_model=List[UserResponseSchema])
def get_users(
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_role(["HR_MANAGER", "ADMIN"]))
):
    """List all registered employee accounts."""
    return list_all_users(db)

@router.patch("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: ResetPasswordSchema,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_role(["HR_MANAGER", "ADMIN"]))
):
    """Reset an employee's password."""
    return reset_user_password(db, hr_user.id, user_id, payload)