import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.modules.admin.ai_chat.agents.base import BaseAgent, AgentResult, AgentStatus
from backend.shared.ai.session_manager import session_manager
from backend.shared.ai.gemini import extract_steel_slots_from_prompt
from backend.modules.admin.steel_estimator.tools import (
    normalize_project_input,
    validate_project_input,
    find_similar_historical_projects,
    analyze_historical_steel_usage,
    calculate_foundation_steel,
    calculate_basement_steel,
    calculate_ground_floor_steel,
    calculate_upper_floor_steel,
    calculate_roof_steel,
    aggregate_steel_estimate,
    get_grade60_market_price,
    calculate_steel_material_cost,
    calculate_estimate_confidence,
)

logger = logging.getLogger("buildora.agents.steel")


class SteelEstimationAgent(BaseAgent):
    """
    Agent responsible for structural steel takeoff estimation.
    Collects required project inputs, validates data using modular tools,
    runs deterministic calculations, analyzes historical data, conditionally fetches market prices,
    and returns auditable results with deterministic confidence scoring.
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
        steel_ctx = session.get("steel_context", {})
        awaiting_slot = session_manager.get_awaiting_slot(sess_id)

        # 1. Extract slots from user message using NLP helper
        extracted = extract_steel_slots_from_prompt(message, awaiting_slot, steel_ctx)
        steel_ctx = session_manager.update_steel_context(sess_id, extracted)

        # 2. Tool 1: Normalize project input
        norm_inputs = normalize_project_input(steel_ctx)

        # 3. Tool 2: Validate project input
        val_result = validate_project_input(norm_inputs)

        if not val_result["is_valid"]:
            missing = val_result["missing_fields"]
            next_missing = missing[0] if missing else "total_covered_area_sqft"
            session_manager.set_awaiting_slot(sess_id, next_missing)
            logger.info(f"SteelEstimationAgent needs input for: {missing}")
            return AgentResult(
                agent="SteelEstimationAgent",
                status=AgentStatus.NEEDS_INPUT,
                missing_fields=missing,
                context_for_llm={
                    "current_state": norm_inputs,
                    "next_prompt_field": next_missing,
                    "missing_fields": missing,
                    "validation_errors": val_result["errors"],
                }
            )

        # Inputs are valid and complete!
        session_manager.set_awaiting_slot(sess_id, None)
        logger.info(f"SteelEstimationAgent executing tool pipeline for {norm_inputs.get('total_covered_area_sqft')} sqft ({norm_inputs.get('building_type')}) at {norm_inputs.get('location')}")

        # 4. Tool 3: Find similar historical projects
        hist_data = find_similar_historical_projects(db, norm_inputs)

        # 5. Tools 5-9: Component calculation supporting breakdown
        comp_foundation = calculate_foundation_steel(db, norm_inputs, hist_data)
        comp_basement = calculate_basement_steel(db, norm_inputs, hist_data)
        comp_ground = calculate_ground_floor_steel(db, norm_inputs, hist_data)
        comp_upper = calculate_upper_floor_steel(db, norm_inputs, hist_data)
        comp_roof = calculate_roof_steel(db, norm_inputs, hist_data)

        components = {
            "foundation": comp_foundation,
            "basement": comp_basement,
            "ground": comp_ground,
            "upper_floor": comp_upper,
            "roof": comp_roof,
        }

        # 6. Tool 10: Aggregate whole-project historical steel estimate & material cost
        agg_estimate = aggregate_steel_estimate(db, norm_inputs, components, similarity_result=hist_data, fetch_market_price=True)

        result_payload = agg_estimate

        # Reset steel context after complete execution
        session_manager.clear_steel_context(sess_id)

        return AgentResult(
            agent="SteelEstimationAgent",
            status=AgentStatus.COMPLETED,
            data=result_payload,
            context_for_llm={
                "type": "steel_takeoff_result",
                "payload": result_payload,
            }
        )
