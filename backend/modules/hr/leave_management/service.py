from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.db.models import LeaveRequest, User, AuditLog
from backend.modules.hr.leave_management.schemas import CreateLeaveRequestSchema, LeaveResponseSchema

def get_user_remaining_leave_days(db: Session, user_id: int, annual_entitlement: int = 15) -> int:
    """Calculates remaining annual leave days based on APPROVED requests only."""
    approved_leaves = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == user_id,
        LeaveRequest.status == "APPROVED"
    ).all()
    used_days = sum(l.days for l in approved_leaves)
    return max(0, annual_entitlement - used_days)

def submit_leave_request(db: Session, user: User, payload: CreateLeaveRequestSchema):
    num_days = (payload.end_date - payload.start_date).days + 1
    if num_days <= 0:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    remaining = get_user_remaining_leave_days(db, user.id)

    if num_days > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"You currently have {remaining} annual leave days remaining, so a {num_days}-day leave request cannot be processed."
        )

    # Business rule: Auto-approval for requests <= 3 days when balance is sufficient
    auto_approve = (num_days <= 3) and (num_days <= remaining)
    initial_status = "APPROVED" if auto_approve else "PENDING"

    leave = LeaveRequest(
        user_id=user.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        days=num_days,
        reason=payload.reason,
        status=initial_status,
        auto_approved=auto_approve
    )
    db.add(leave)
    
    audit = AuditLog(
        user_id=user.id,
        action="LEAVE_REQUEST",
        details=f"User submitted leave request for {num_days} day(s). Status: {initial_status}."
    )
    db.add(audit)
    
    db.commit()
    db.refresh(leave)
    return leave

def list_all_leave_requests(db: Session):
    leaves = db.query(LeaveRequest).order_by(LeaveRequest.created_at.desc()).all()
    results = []
    for l in leaves:
        user = db.query(User).filter(User.id == l.user_id).first()
        results.append(LeaveResponseSchema(
            id=l.id,
            user_id=l.user_id,
            user_name=user.full_name if user else "Unknown User",
            start_date=l.start_date,
            end_date=l.end_date,
            days=l.days,
            reason=l.reason,
            status=l.status,
            auto_approved=l.auto_approved,
            created_at=l.created_at
        ))
    return results

def update_leave_approval_status(db: Session, hr_id: int, leave_id: int, new_status: str):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    if new_status.upper() == "APPROVED" and leave.status != "APPROVED":
        # Mandatory balance re-check before HR approval
        remaining = get_user_remaining_leave_days(db, leave.user_id)
        if leave.days > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve request: user has only {remaining} remaining leave day(s), but request is for {leave.days} day(s)."
            )

    leave.status = new_status.upper()
    audit = AuditLog(
        user_id=hr_id,
        action="LEAVE_STATUS_UPDATE",
        details=f"HR Manager updated leave #{leave_id} status to {new_status.upper()}."
    )
    db.add(audit)
    db.commit()
    db.refresh(leave)
    return leave