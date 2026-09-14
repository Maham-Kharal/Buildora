from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.db.models import LeaveRequest, User, AuditLog
from backend.modules.hr.leave_management.schemas import CreateLeaveRequestSchema, LeaveResponseSchema

def submit_leave_request(db: Session, user: User, payload: CreateLeaveRequestSchema):
    num_days = (payload.end_date - payload.start_date).days + 1
    if num_days <= 0:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    # Business rule: Auto-approval for requests < 3 days
    auto_approve = num_days < 3
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
    
    leave.status = new_status
    audit = AuditLog(
        user_id=hr_id,
        action="LEAVE_STATUS_UPDATE",
        details=f"HR Manager updated leave #{leave_id} status to {new_status}."
    )
    db.add(audit)
    db.commit()
    db.refresh(leave)
    return leave