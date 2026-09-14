from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.deps import get_db, get_current_user
from backend.modules.auth.schemas import LoginRequestSchema, TokenSchema
from backend.modules.auth.service import authenticate_user
from backend.db.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenSchema)
def login(login_data: LoginRequestSchema, db: Session = Depends(get_db)):
    """Authenticate user with email and password, returning JWT access token."""
    return authenticate_user(db, login_data)

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return authenticated user profile details."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role
    }
