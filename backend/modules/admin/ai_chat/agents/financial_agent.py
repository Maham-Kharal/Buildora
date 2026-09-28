import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.modules.admin.ai_chat.agents.base import BaseAgent, AgentResult, AgentStatus
from backend.shared.ai.session_manager import session_manager
from backend.shared.ai.gemini import extract_expense_filters_with_gemini
from backend.shared.ai.tools import query_financial_expenses_db

logger = logging.getLogger("buildora.agents.financial")


class FinancialReportAgent(BaseAgent):
    """
    Agent responsible for corporate financial expense reports and spending analytics.
    Extracts date ranges, worker filters, project filters, category filters,
    queries verified receipt records, calculates totals, and returns trusted data.
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
        curr_exp_ctx = session_manager.get_expense_filter_context(sess_id)

        # Extract expense criteria from prompt
        extracted = extract_expense_filters_with_gemini(message, curr_exp_ctx)
        active_exp_ctx = session_manager.update_expense_filter_context(sess_id, extracted)

        logger.info(f"FinancialReportAgent executing query with filters: {active_exp_ctx}")

        # Query database via trusted tool/service
        financial_payload = query_financial_expenses_db(
            db,
            prompt=message,
            start_date=active_exp_ctx.get("start_date"),
            end_date=active_exp_ctx.get("end_date"),
            project_filter=active_exp_ctx.get("project_filter"),
            user_filter=active_exp_ctx.get("user_filter"),
            category_filter=active_exp_ctx.get("category_filter"),
            min_amount=active_exp_ctx.get("min_amount"),
            max_amount=active_exp_ctx.get("max_amount")
        )

        return AgentResult(
            agent="FinancialReportAgent",
            status=AgentStatus.COMPLETED,
            data=financial_payload,
            context_for_llm={
                "type": "financial_report_payload",
                "payload": financial_payload,
            }
        )
