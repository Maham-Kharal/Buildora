from pydantic import BaseModel
from typing import Optional

class HRAssistantQuerySchema(BaseModel):
    prompt: str
    session_id: Optional[str] = "default_session"
    role: Optional[str] = None

class HRAssistantResponseSchema(BaseModel):
    answer: str
    auto_approved_leave: bool = False
    intent: Optional[str] = None
    session_id: Optional[str] = "default_session"
