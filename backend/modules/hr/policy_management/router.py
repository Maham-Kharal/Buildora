from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.deps import get_db, get_current_user, require_role
from backend.db.models import User
from backend.modules.hr.policy_management.schemas import CreatePolicySchema, PolicyResponseSchema
from backend.modules.hr.policy_management.service import add_company_policy, list_company_policies, delete_company_policy

router = APIRouter(prefix="/hr/policies", tags=["HR - Company Policy Management"])

@router.post("", response_model=PolicyResponseSchema)
def create_policy(
    payload: CreatePolicySchema,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_role(["HR_MANAGER", "ADMIN"]))
):
    """Add a new company policy document for HR KB knowledge base."""
    return add_company_policy(db, hr_user.id, payload)

@router.get("", response_model=List[PolicyResponseSchema])
def get_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve company policy documents."""
    return list_company_policies(db)

@router.delete("/{policy_id}")
def remove_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_role(["HR_MANAGER", "ADMIN"]))
):
    """Delete a company policy document."""
    return delete_company_policy(db, hr_user.id, policy_id)
