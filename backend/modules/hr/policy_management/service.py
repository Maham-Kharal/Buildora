from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.db.models import CompanyPolicy, AuditLog
from backend.modules.hr.policy_management.schemas import CreatePolicySchema

def add_company_policy(db: Session, hr_id: int, payload: CreatePolicySchema):
    policy = CompanyPolicy(
        title=payload.title,
        category=payload.category,
        content=payload.content
    )
    db.add(policy)
    
    audit = AuditLog(
        user_id=hr_id,
        action="CREATE_POLICY",
        details=f"HR Manager added company policy document '{payload.title}'."
    )
    db.add(audit)
    db.commit()
    db.refresh(policy)
    return policy

def list_company_policies(db: Session):
    return db.query(CompanyPolicy).order_by(CompanyPolicy.created_at.desc()).all()

def delete_company_policy(db: Session, hr_id: int, policy_id: int):
    policy = db.query(CompanyPolicy).filter(CompanyPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy document not found")
    
    db.delete(policy)
    audit = AuditLog(
        user_id=hr_id,
        action="DELETE_POLICY",
        details=f"HR Manager deleted policy document ID #{policy_id}."
    )
    db.add(audit)
    db.commit()
    return {"message": "Policy document deleted successfully"}
