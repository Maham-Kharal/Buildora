from fastapi import APIRouter, Depends, Header
from typing import Optional
from sqlalchemy.orm import Session
from backend.core.deps import get_db
from backend.core.config import settings
from backend.db.models import User
from jose import jwt
from backend.modules.user.hr_assistant.schemas import HRAssistantQuerySchema, HRAssistantResponseSchema
from backend.modules.user.hr_assistant.service import handle_hr_query

router = APIRouter(prefix="/user/hr-assistant", tags=["AI Assistant Engine"])

def get_assistant_user(db: Session = Depends(get_db), authorization: Optional[str] = Header(None)) -> User:
    """Retrieve authenticated user from JWT token or fall back to system user."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    return user
        except Exception:
            pass
    user = db.query(User).first()
    if not user:
        user = User(email="admin@buildora.com", full_name="Admin User", role="ADMIN")
    return user

@router.post("/ask", response_model=HRAssistantResponseSchema)
def ask_hr_assistant(
    data: HRAssistantQuerySchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_assistant_user)
):
    """Stateful AI Query endpoint for Admin operations or Worker assistant."""
    return handle_hr_query(
        db=db,
        user=current_user,
        prompt=data.prompt,
        session_id=data.session_id or "default_session",
        client_role=data.role
    )