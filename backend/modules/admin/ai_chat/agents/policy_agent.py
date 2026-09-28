import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.modules.admin.ai_chat.agents.base import BaseAgent, AgentResult, AgentStatus
from backend.shared.ai.tools import query_company_policy_kb

logger = logging.getLogger("buildora.agents.policy")


class PolicyAgent(BaseAgent):
    """
    Agent responsible for company policy knowledge base queries using Qdrant RAG.
    Retrieves semantic chunks from Qdrant vector store and returns structured context.
    """

    async def execute(
        self,
        *,
        message: str,
        session: Dict[str, Any],
        db: Session,
        current_user: User,
    ) -> AgentResult:
        logger.info(f"PolicyAgent searching Qdrant policy knowledge base for message: '{message}'")
        sources = query_company_policy_kb(db, message)

        if sources and len(sources) > 0:
            status = AgentStatus.COMPLETED
            logger.info(f"POLICY_AGENT result=COMPLETED (sources_found={len(sources)})")
            context = {
                "type": "company_policy_payload",
                "query": message,
                "sources": sources,
            }
        else:
            status = AgentStatus.NOT_FOUND
            logger.info("POLICY_AGENT result=NOT_FOUND")
            context = {
                "type": "company_policy_payload",
                "query": message,
                "sources": [],
                "message": "No relevant company policy documents found."
            }

        return AgentResult(
            agent="PolicyAgent",
            status=status,
            data={"sources": sources, "count": len(sources)},
            context_for_llm=context
        )
