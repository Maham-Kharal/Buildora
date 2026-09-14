from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.deps import get_db, get_current_user, require_role
from backend.db.models import User
from backend.modules.hr.leave_management.schemas import CreateLeaveRequestSchema, UpdateLeaveStatusSchema, LeaveResponseSchema
from backend.modules.hr.leave_management.service import submit_leave_request, list_all_leave_requests, update_leave_approval_status

router = APIRouter(prefix="/hr/leaves", tags=["HR - Leave Management"])

@router.post("", response_model=LeaveResponseSchema)
def request_leave(
    payload: CreateLeaveRequestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit a leave request. Requests under 3 days are auto-approved."""
    return submit_leave_request(db, current_user, payload)

@router.get("", response_model=List[LeaveResponseSchema])
def get_leaves(
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_role(["HR_MANAGER", "ADMIN"]))
):
    """List all employee leave requests for HR review."""
    return list_all_leave_requests(db)

@router.patch("/{leave_id}/status")
def update_status(
    leave_id: int,
    payload: UpdateLeaveStatusSchema,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_role(["HR_MANAGER", "ADMIN"]))
):
    """Approve or Reject an employee leave request."""
    return update_leave_approval_status(db, hr_user.id, leave_id, payload.status)