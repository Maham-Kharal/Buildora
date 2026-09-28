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

        # 2. Determine Intent (preserve active multi-turn agent state or classify new intent)
        steel_ctx = session.get("steel_context", {})
        active_slot = session_manager.get_awaiting_slot(session_id)
        
        # Check topic switching or explicit reset commands
        msg_lower = message.lower().strip()
        is_explicit_reset = any(k in msg_lower for k in ["cancel", "reset", "start over", "clear"])

        if is_explicit_reset:
            session_manager.clear_steel_context(session_id)
            session_manager.clear_expense_filter_context(session_id)
            session_manager.clear_project_filter_context(session_id)
            session["active_intent"] = IntentEnum.GENERAL_CONVERSATION.value

        if steel_ctx.get("active") and active_slot and not is_explicit_reset:
            # Check if user is switching topic to another distinct domain
            raw_intent_str = classify_intent_with_gemini(message)
            if raw_intent_str in [IntentEnum.FINANCIAL_REPORT.value, IntentEnum.PROJECT_HISTORY.value, IntentEnum.COMPANY_POLICY.value]:
                intent = IntentEnum(raw_intent_str)
                session_manager.clear_steel_context(session_id)
                logger.info(f"Topic switch detected from active steel slot to intent={intent.value}")
            else:
                intent = IntentEnum.STEEL_ESTIMATION
                logger.info(f"Preserving active multi-turn slot for intent=steel_estimation (awaiting_slot={active_slot})")
        else:
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
