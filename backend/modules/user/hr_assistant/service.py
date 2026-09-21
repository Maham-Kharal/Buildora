from typing import Optional
from sqlalchemy.orm import Session
from backend.db.models import User
from backend.shared.ai.gemini import process_unified_ai_assistant_query

def handle_hr_query(
    db: Session,
    user: User,
    prompt: str,
    session_id: Optional[str] = "default_session",
    client_role: Optional[str] = None
):
    user_role = client_role if client_role else (user.role if user and hasattr(user, 'role') else "WORKER")
    
    response = process_unified_ai_assistant_query(
        prompt=prompt,
        db=db,
        current_user=user,
        user_role=user_role,
        session_id=session_id
    )
    response["session_id"] = session_id
    return response
