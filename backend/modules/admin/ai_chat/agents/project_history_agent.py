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
    Filters by covered area, structural system, floors, foundation type, steel tonnage, and location.
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
        msg_lower = message.lower().strip()

        # Check unsupported filters (e.g. budget, cost, price, team, members)
        unsupported = any(k in msg_lower for k in ["budget", "cost", "price", "$", "million", "team", "members"])
        if unsupported:
            return AgentResult(
                agent="ProjectHistoryAgent",
                status=AgentStatus.COMPLETED,
                data={"unsupported_filter": True},
                context_for_llm={
                    "type": "project_history_unsupported",
                    "message": "Historical project budget is not stored in the current dataset. I can filter by area, steel quantity, location, building type, floors, structural system, foundation type, or floor system."
                }
            )

        curr_proj_ctx = session_manager.get_project_filter_context(sess_id)
        extracted = extract_project_filters_with_gemini(message, curr_proj_ctx)
        active_proj_ctx = session_manager.update_project_filter_context(sess_id, extracted)

        # Check if user prompt gave NO search conditions (vague request)
        has_active_filters = any(
            v is not None for k, v in active_proj_ctx.items() if k != "active"
        )
        if not has_active_filters:
            return AgentResult(
                agent="ProjectHistoryAgent",
                status=AgentStatus.NEEDS_INPUT,
                data={"vague": True},
                context_for_llm={
                    "type": "project_history_vague",
                    "message": "What kind of historical projects would you like to see? You can filter by area, steel quantity, location, building type, floors, structural system, foundation type, or floor system."
                }
            )

        logger.info(f"ProjectHistoryAgent executing DB query with filters: {active_proj_ctx}")

        proj_payload = query_historical_projects_db(
            db,
            min_sqft=active_proj_ctx.get("min_sqft"),
            max_sqft=active_proj_ctx.get("max_sqft"),
            building_type=active_proj_ctx.get("building_type"),
            structural_system=active_proj_ctx.get("structural_system"),
            floors=active_proj_ctx.get("floors"),
            foundation_type=active_proj_ctx.get("foundation_type"),
            floor_system=active_proj_ctx.get("floor_system"),
            min_steel_tons=active_proj_ctx.get("min_steel_tons"),
            max_steel_tons=active_proj_ctx.get("max_steel_tons"),
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
