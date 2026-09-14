from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.db.models import User, AuditLog
from backend.core.security import get_password_hash
from backend.modules.hr.user_management.schemas import (
    CreateUserSchema, ResetPasswordSchema, UserCreateRequest, PasswordResetRequest
)

def create_new_user(db: Session, hr_id: int, user_data: CreateUserSchema):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    hashed_pwd = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=hashed_pwd,
        role=user_data.role,
        is_active=True
    )
    db.add(user)
    
    audit = AuditLog(
        user_id=hr_id,
        action="CREATE_USER",
        details=f"HR Manager created user {user_data.email} with role {user_data.role}."
    )
    db.add(audit)
    
    db.commit()
    db.refresh(user)
    return user

def list_all_users(db: Session):
    return db.query(User).order_by(User.id.asc()).all()

def reset_user_password(db: Session, hr_id: int, target_user_id: int, payload: ResetPasswordSchema):
    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.password_hash = get_password_hash(payload.new_password)
    audit = AuditLog(
        user_id=hr_id,
        action="RESET_PASSWORD",
        details=f"HR Manager reset password for user ID #{target_user_id} ({user.email})."
    )
    db.add(audit)
    db.commit()
    return {"message": f"Password reset successfully for user {user.email}"}
