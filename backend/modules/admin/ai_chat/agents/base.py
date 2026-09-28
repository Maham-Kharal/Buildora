from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.db.models import User


class AgentStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class AgentResult(BaseModel):
    agent: str
    status: AgentStatus
    data: Optional[Dict[str, Any]] = None
    missing_fields: List[str] = []
    context_for_llm: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract Base Class for all domain-specific Buildora agents.
    Agents own one domain workflow, validate inputs, execute backend tools/services,
    and return a structured AgentResult to the Orchestrator.
    """

    @abstractmethod
    async def execute(
        self,
        *,
        message: str,
        session: Dict[str, Any],
        db: Session,
        current_user: User,
    ) -> AgentResult:
        pass
