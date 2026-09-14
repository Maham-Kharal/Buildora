from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.deps import get_db, get_current_user
from backend.db.models import User
from backend.modules.user.hr_assistant.schemas import HRAssistantQuerySchema, HRAssistantResponseSchema
from backend.modules.user.hr_assistant.service import handle_hr_query

router = APIRouter(prefix="/user/hr-assistant", tags=["Worker - HR Assistant Drawer"])

@router.post("/ask", response_model=HRAssistantResponseSchema)
def ask_hr_assistant(
    data: HRAssistantQuerySchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Query AI HR Assistant for policy guidance or leave requests with security guardrails."""
    return handle_hr_query(db, current_user, data.prompt)