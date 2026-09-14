from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.db.models import User
from backend.core.security import verify_password, create_access_token
from backend.modules.auth.schemas import LoginRequestSchema, TokenSchema

def authenticate_user(db: Session, login_data: LoginRequestSchema) -> TokenSchema:
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated"
        )

    token = create_access_token(subject=user.id, role=user.role)
    return TokenSchema(
        access_token=token,
        role=user.role,
        user_id=user.id,
        full_name=user.full_name
    )