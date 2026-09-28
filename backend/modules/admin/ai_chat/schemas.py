from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any


class IntentEnum(str, Enum):
    STEEL_ESTIMATION = "steel_estimation"
    FINANCIAL_REPORT = "financial_report"
    PROJECT_HISTORY = "project_history"
    COMPANY_POLICY = "company_policy"
    GENERAL_CONVERSATION = "general_conversation"


class AiChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_admin_session"


class AiChatResponse(BaseModel):
    session_id: str
    message: str
    intent: Optional[str] = None
    agent: Optional[str] = None
    status: str = "completed"
    data: Optional[Dict[str, Any]] = None
