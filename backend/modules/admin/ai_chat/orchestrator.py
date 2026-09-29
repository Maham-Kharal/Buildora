import logging
from typing import Dict, Any, Type
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.shared.ai.session_manager import session_manager
from backend.shared.ai.gemini import classify_intent_with_gemini, format_agent_explanation_with_gemini
from backend.modules.admin.ai_chat.schemas import IntentEnum
from backend.modules.admin.ai_chat.agents.base import BaseAgent, AgentResult, AgentStatus
from backend.modules.admin.ai_chat.agents.steel_agent import SteelEstimationAgent
from backend.modules.admin.ai_chat.agents.financial_agent import FinancialReportAgent
from backend.modules.admin.ai_chat.agents.project_history_agent import ProjectHistoryAgent
from backend.modules.admin.ai_chat.agents.policy_agent import PolicyAgent
from backend.modules.admin.ai_chat.agents.general_agent import GeneralAgent

logger = logging.getLogger("buildora.orchestrator")

# -----------------------------------------------------------------------
# BACKEND AGENT REGISTRY (Controlled Backend Python Registry)
# -----------------------------------------------------------------------
AGENT_REGISTRY: Dict[IntentEnum, BaseAgent] = {
    IntentEnum.STEEL_ESTIMATION: SteelEstimationAgent(),
    IntentEnum.FINANCIAL_REPORT: FinancialReportAgent(),
    IntentEnum.PROJECT_HISTORY: ProjectHistoryAgent(),
    IntentEnum.COMPANY_POLICY: PolicyAgent(),
    IntentEnum.GENERAL_CONVERSATION: GeneralAgent(),
}


class BuildoraOrchestrator:
    """
    Buildora AI Systems Orchestrator.
    - Python backend owns workflow orchestration, authorization, and tool execution.
    - Gemini handles natural language intent classification and response explanation.
    - Gemini NEVER executes backend tools or chooses Python execution paths directly.
    """

    async def orchestrate(
        self,
        *,
        message: str,
        session_id: str,
        db: Session,
        current_user: User,
    ) -> Dict[str, Any]:
        # 1. Load session context
        session = session_manager.get_session(session_id)
        session["session_id"] = session_id
        logger.info(f"AI_CHAT request received from user_id={current_user.id} | SESSION loaded id={session_id}")

        # 2. Determine Intent (Precedence: 1. Explicit Domain Switch -> 2. Plain Reset -> 3. Active Workflow Lock -> 4. New Global Intent)
        steel_ctx = session.get("steel_context", {})
        msg_lower = message.lower().strip()
        
        # Explicit switch / cancel triggers
        explicit_history_switch = any(k in msg_lower for k in [
            "show historical projects", "search historical projects", "find past projects",
            "list historical projects", "view past projects", "show projects over",
            "show projects larger", "show projects under", "show projects with", "historical project search",
            "historical projects"
        ])
        explicit_financial_switch = any(k in msg_lower for k in [
            "show expense report", "financial report", "show expenses", "expense report",
            "monthly expense", "weekly expense", "today's expense", "daily expense"
        ])
        explicit_policy_switch = any(k in msg_lower for k in [
            "company policy", "hr policy", "leave policy", "safety policy"
        ])
        is_explicit_reset = any(k in msg_lower for k in ["cancel", "reset", "start over", "clear", "forget this estimate", "abandon"])

        if explicit_history_switch:
            session_manager.clear_steel_context(session_id)
            intent = IntentEnum.PROJECT_HISTORY
            logger.info("Explicit switch to ProjectHistoryAgent detected.")
        elif explicit_financial_switch:
            session_manager.clear_steel_context(session_id)
            intent = IntentEnum.FINANCIAL_REPORT
            logger.info("Explicit switch to FinancialReportAgent detected.")
        elif explicit_policy_switch:
            session_manager.clear_steel_context(session_id)
            intent = IntentEnum.COMPANY_POLICY
            logger.info("Explicit switch to PolicyAgent detected.")
        elif is_explicit_reset:
            session_manager.clear_steel_context(session_id)
            session_manager.clear_expense_filter_context(session_id)
            session_manager.clear_project_filter_context(session_id)
            intent = IntentEnum.GENERAL_CONVERSATION
            logger.info("Explicit reset command executed — cleared session contexts.")
        elif steel_ctx.get("active"):
            # Active steel session lock: retain SteelEstimationAgent without running global intent classifier
            intent = IntentEnum.STEEL_ESTIMATION
            logger.info("Preserving active steel_estimation workflow lock.")
        else:
            # New workflow intent classification
            raw_intent_str = classify_intent_with_gemini(message)
            try:
                intent = IntentEnum(raw_intent_str)
            except ValueError:
                intent = IntentEnum.GENERAL_CONVERSATION

        logger.info(f"ORCHESTRATOR classified intent={intent.value}")
        session["active_intent"] = intent.value

        # 3. Select registered agent from AGENT_REGISTRY
        agent_instance = AGENT_REGISTRY.get(intent, AGENT_REGISTRY[IntentEnum.GENERAL_CONVERSATION])
        logger.info(f"ORCHESTRATOR selected agent={agent_instance.__class__.__name__}")

        # 4. Execute domain agent (Agent runs domain tools/calculations)
        agent_result: AgentResult = await agent_instance.execute(
            message=message,
            session=session,
            db=db,
            current_user=current_user,
        )

        logger.info(f"AGENT {agent_result.agent} returned status={agent_result.status.value}")

        # 5. Format trusted AgentResult into natural response via Gemini
        logger.info("GEMINI response generation started")
        llm_context = agent_result.context_for_llm or (agent_result.data if agent_result.data else {})
        natural_response = format_agent_explanation_with_gemini(
            user_message=message,
            agent_name=agent_result.agent,
            status=agent_result.status.value,
            context_data=llm_context
        )
        logger.info("GEMINI response generation completed")

        return {
            "session_id": session_id,
            "message": natural_response,
            "intent": intent.value,
            "agent": agent_result.agent,
            "status": agent_result.status.value,
            "data": agent_result.data,
        }


orchestrator = BuildoraOrchestrator()
