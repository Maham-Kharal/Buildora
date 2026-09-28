import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.modules.admin.ai_chat.agents.base import BaseAgent, AgentResult, AgentStatus
from backend.shared.ai.session_manager import session_manager
from backend.shared.ai.gemini import extract_project_filters_with_gemini
from backend.shared.ai.tools import query_historical_projects_db

logger = logging.getLogger("buildora.agents.project_history")


class ProjectHistoryAgent(BaseAgent):
    """
    Agent responsible for querying historical project database records.
    Filters by covered area, structural system, floors, foundation type, budget, steel tonnage, and location.
    """

    async def execute(
        self,
        *,
        message: str,
        session: Dict[str, Any],
        db: Session,
        current_user: User,
    ) -> AgentResult:
        sess_id = session.get("session_id", "default_admin_session")
        curr_proj_ctx = session_manager.get_project_filter_context(sess_id)

        # Extract project criteria
        extracted = extract_project_filters_with_gemini(message, curr_proj_ctx)
        active_proj_ctx = session_manager.update_project_filter_context(sess_id, extracted)

        logger.info(f"ProjectHistoryAgent executing DB query with filters: {active_proj_ctx}")

        proj_payload = query_historical_projects_db(
            db,
            min_sqft=active_proj_ctx.get("min_sqft"),
            max_sqft=active_proj_ctx.get("max_sqft"),
            structural_system=active_proj_ctx.get("structural_system"),
            floors=active_proj_ctx.get("floors"),
            foundation_type=active_proj_ctx.get("foundation_type"),
            min_steel_tons=active_proj_ctx.get("min_steel_tons"),
            max_steel_tons=active_proj_ctx.get("max_steel_tons"),
            min_budget=active_proj_ctx.get("min_budget"),
            max_budget=active_proj_ctx.get("max_budget"),
            location_filter=active_proj_ctx.get("location")
        )

        status = AgentStatus.COMPLETED if proj_payload.get("matching_count", 0) > 0 else AgentStatus.NOT_FOUND

        return AgentResult(
            agent="ProjectHistoryAgent",
            status=status,
            data=proj_payload,
            context_for_llm={
                "type": "project_history_payload",
                "payload": proj_payload,
            }
        )
