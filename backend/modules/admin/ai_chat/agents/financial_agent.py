import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.modules.admin.ai_chat.agents.base import BaseAgent, AgentResult, AgentStatus
from backend.shared.ai.session_manager import session_manager
from backend.shared.ai.gemini import extract_expense_filters_with_gemini
from backend.shared.ai.tools import query_financial_expenses_db

logger = logging.getLogger("buildora.agents.financial")


import logging
import re
import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from backend.db.models import User, ActiveProject
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
        msg_lower = message.lower().strip()
        curr_exp_ctx = session_manager.get_expense_filter_context(sess_id)

        # 1. Check project filter matching
        active_projs = db.query(ActiveProject).all()
        matched_projects = []
        for ap in active_projs:
            if ap.name.lower() in msg_lower:
                matched_projects.append(ap)

        if not matched_projects:
            m = re.search(r'\b(?:for|on|in)\s+(?:project\s+)?([a-zA-Z0-9\s]+)\b', message, re.IGNORECASE)
            if m:
                cand = m.group(1).strip()
                stop_words = ["today", "this week", "this month", "daily", "weekly", "monthly", "expense", "expenses", "report", "spending", "all"]
                if cand and cand.lower() not in stop_words and len(cand) > 2:
                    for ap in active_projs:
                        if cand.lower() in ap.name.lower() or ap.name.lower() in cand.lower():
                            matched_projects.append(ap)
                    if not matched_projects:
                        return AgentResult(
                            agent="FinancialReportAgent",
                            status=AgentStatus.NOT_FOUND,
                            data={"unknown_project": True},
                            context_for_llm={
                                "type": "financial_unknown_project",
                                "message": f"I couldn't find an active project named '{cand}'."
                            }
                        )

        if matched_projects:
            distinct_names = list(dict.fromkeys([p.name for p in matched_projects]))
            if len(distinct_names) > 1:
                return AgentResult(
                    agent="FinancialReportAgent",
                    status=AgentStatus.NEEDS_INPUT,
                    data={"ambiguous_projects": distinct_names},
                    context_for_llm={
                        "type": "financial_ambiguous_project",
                        "message": f"I found more than one project named '{distinct_names[0]}'. Which project do you mean?"
                    }
                )
            selected_proj_name = distinct_names[0]
        else:
            selected_proj_name = curr_exp_ctx.get("project_filter")

        # 2. Extract expense criteria
        extracted = extract_expense_filters_with_gemini(message, curr_exp_ctx)
        if selected_proj_name:
            extracted["project_filter"] = selected_proj_name

        active_exp_ctx = session_manager.update_expense_filter_context(sess_id, extracted)

        # 3. Check generic all-period request ("give me the expense report", "show expense reports")
        is_generic = any(
            k in msg_lower for k in [
                "give me the expense report", "show expense reports", "i want the financial report",
                "give me all expense reports", "show all expense reports", "expense report", "financial report"
            ]
        ) and not any(
            k in msg_lower for k in ["today", "this week", "this month", "daily", "weekly", "monthly", "september", "august", "october"]
        )

        if is_generic and not selected_proj_name:
            today = datetime.date.today()
            today_report = query_financial_expenses_db(db, start_date=today, end_date=today)
            
            week_start = today - datetime.timedelta(days=7)
            week_report = query_financial_expenses_db(db, start_date=week_start, end_date=today)
            
            month_start = today.replace(day=1)
            month_report = query_financial_expenses_db(db, start_date=month_start, end_date=today)

            combined_payload = {
                "today": today_report,
                "weekly": week_report,
                "monthly": month_report,
            }

            return AgentResult(
                agent="FinancialReportAgent",
                status=AgentStatus.COMPLETED,
                data=combined_payload,
                context_for_llm={
                    "type": "financial_combined_summary",
                    "payload": combined_payload,
                }
            )

        # 4. Single period or project-filtered query
        logger.info(f"FinancialReportAgent executing query with filters: {active_exp_ctx}")

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
