from sqlalchemy.orm import Session
from backend.db.models import User, CompanyPolicy, LeaveRequest
from backend.shared.ai.gemini import query_hr_assistant

def handle_hr_query(db: Session, user: User, prompt: str):
    policies = db.query(CompanyPolicy).all()
    policy_docs = [{"title": p.title, "content": p.content} for p in policies]
    
    # Calculate user leave balance (default 15 days allowance minus approved leaves)
    used_leaves = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == user.id,
        LeaveRequest.status == "APPROVED"
    ).all()
    
    days_used = sum([l.days for l in used_leaves])
    active_balance = max(0, 15 - days_used)

    response = query_hr_assistant(prompt, policy_docs, active_balance)
    return response
