import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.modules.admin.ai_chat.agents.base import BaseAgent, AgentResult, AgentStatus

logger = logging.getLogger("buildora.agents.general")


class GeneralAgent(BaseAgent):
    """
    Agent responsible for general conversation, greetings, and platform capability guidance.
    Does not execute domain database tools.
    """

    async def execute(
        self,
        *,
        message: str,
        session: Dict[str, Any],
        db: Session,
        current_user: User,
    ) -> AgentResult:
        logger.info("GeneralAgent handling conversational query.")
        return AgentResult(
            agent="GeneralAgent",
            status=AgentStatus.COMPLETED,
            data={"greeting": True},
            context_for_llm={
                "type": "general_conversation",
                "capabilities": [
                    "Structural Steel Takeoff Estimation",
                    "Financial Expense Reports & Analytics",
                    "Past Construction Project History Database",
                    "Buildora Company Policies & Safety Protocols"
                ]
            }
        )
