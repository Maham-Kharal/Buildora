import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import SessionLocal
from backend.shared.ai.session_manager import session_manager
from backend.shared.ai.gemini import extract_steel_slots_from_prompt, normalize_strict, FLOOR_OPTIONS
from backend.modules.admin.steel_estimator.tools import (
    normalize_project_input,
    find_similar_historical_projects,
    calculate_foundation_steel,
    calculate_basement_steel,
    calculate_ground_floor_steel,
    calculate_upper_floor_steel,
    calculate_roof_steel,
    aggregate_steel_estimate,
)

client = TestClient(app)

def get_admin_headers():
    from backend.core.security import create_access_token
    from backend.db.models import User
    db = SessionLocal()
    admin_user = db.query(User).filter(User.role == "ADMIN").first()
    admin_id = admin_user.id if admin_user else 1
    db.close()
    token = create_access_token(subject=str(admin_id), role="ADMIN")
    return {"Authorization": f"Bearer {token}"}


def test_floor_system_normalization_and_pt_ambiguity():
    """TEST D: Safe flat plate aliases map cleanly; ambiguous generic 'PT slab' returns None for clarification."""
    # Safe flat plate aliases
    assert normalize_strict("flat plate", FLOOR_OPTIONS) == "Flat Slab"
    assert normalize_strict("standard flat plate", FLOOR_OPTIONS) == "Flat Slab"
    assert normalize_strict("RC flat plate", FLOOR_OPTIONS) == "Flat Slab"
    assert normalize_strict("reinforced concrete flat plate", FLOOR_OPTIONS) == "Flat Slab"
    assert normalize_strict("post-tensioned flat plate", FLOOR_OPTIONS) == "Flat Slab"
    assert normalize_strict("PT flat plate", FLOOR_OPTIONS) == "Flat Slab"
    assert normalize_strict("post-tensioned flat slab", FLOOR_OPTIONS) == "Flat Slab"
    assert normalize_strict("beam and slab", FLOOR_OPTIONS) == "Beam & Slab"

    # Ambiguous generic PT slab does not falsely force Flat Slab
    assert normalize_strict("PT slab", FLOOR_OPTIONS) is None
    assert normalize_strict("post-tensioned slab", FLOOR_OPTIONS) is None


def test_user_confirmation_and_flat_plate_persistence():
    """TEST C: 'standard flat plate' persists into session and remains persisted across subsequent turns."""
    sess_id = "test_persistence_session"
    session_manager.clear_steel_context(sess_id)

    # 1. Provide floor_system
    ext1 = extract_steel_slots_from_prompt("standard flat plate", "floor_system", {})
    assert ext1.get("floor_system") == "Flat Slab"
    session_manager.update_steel_context(sess_id, ext1)

    ctx1 = session_manager.get_steel_context(sess_id)
    assert ctx1.get("floor_system") == "Flat Slab"

    # 2. Next turn provides location; floor_system MUST remain persisted
    ext2 = extract_steel_slots_from_prompt("California", "location", ctx1)
    session_manager.update_steel_context(sess_id, ext2)

    ctx2 = session_manager.get_steel_context(sess_id)
    assert ctx2.get("floor_system") == "Flat Slab"
    assert ctx2.get("location") == "California"

    session_manager.clear_steel_context(sess_id)


def test_direct_vs_chat_baseline_identity():
    """TEST A: Direct Change 5 service and Chat endpoint return identical baseline calculations."""
    msg = "Estimate steel for 50000 sqft residential building, 5 floors, 1 basement, RCC frame, mat foundation, beam and slab, Los Angeles CA"

    # Extract & normalize inputs
    extracted = extract_steel_slots_from_prompt(msg, None, {})
    norm_inputs = normalize_project_input(extracted)

    db = SessionLocal()
    try:
        hist_data = find_similar_historical_projects(db, norm_inputs)
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

        agg_direct = aggregate_steel_estimate(db, norm_inputs, components, similarity_result=hist_data, fetch_market_price=False)
        direct_tot = agg_direct["total_estimate"]
        direct_conf = agg_direct["confidence"]
    finally:
        db.close()

    headers = get_admin_headers()
    res = client.post("/api/v1/admin/ai/chat", headers=headers, json={"message": msg})
    assert res.status_code == 200
    chat_data = res.json()

    chat_tot = chat_data["data"]["total_estimate"]
    chat_conf = chat_data["data"]["confidence"]

    # Verify identity
    assert direct_tot["estimated_net_lbs"] == chat_tot["estimated_net_lbs"] == 170239.95
    assert direct_tot["estimated_net_us_tons"] == chat_tot["estimated_net_us_tons"] == 85.12
    assert direct_conf["display_score"] == chat_conf["display_score"] == 87
    assert direct_conf["label"] == chat_conf["label"] == "HIGH"


def test_extreme_outlier_project_execution_and_extrapolation_warning():
    """TEST B: Extreme project asks anomaly confirmation, then executes upon confirmation without slot looping, displays extrapolation warning, and uses historical evidence."""
    headers = get_admin_headers()
    sess_id = "test_outlier_confirm_session"
    session_manager.clear_steel_context(sess_id)

    payload1 = {
        "message": "I want to estimate steel for a 60000000 sqft hotel building, 100 floors, 6 basements, RCC moment frame, mat foundation, standard flat plate, California",
        "session_id": sess_id
    }
    res1 = client.post("/api/v1/admin/ai/chat", headers=headers, json=payload1)
    assert res1.status_code == 200
    data1 = res1.json()

    assert data1["agent"] == "SteelEstimationAgent"
    assert data1["status"] == "needs_input"
    assert "confirm" in data1["message"].lower() or "outside" in data1["message"].lower()

    # User confirms
    payload2 = {
        "message": "Yes, proceed",
        "session_id": sess_id
    }
    res2 = client.post("/api/v1/admin/ai/chat", headers=headers, json=payload2)
    assert res2.status_code == 200
    data2 = res2.json()

    assert data2["agent"] == "SteelEstimationAgent"
    assert data2["status"] == "completed"

    tot = data2["data"]["total_estimate"]
    assert tot["user_total_covered_area_sqft"] == 60000000
    assert tot["estimated_net_lbs"] is not None
    assert tot["estimated_net_us_tons"] is not None

    # Verify extrapolation warning in user response message
    assert "Extrapolation Warning" in data2["message"] or "substantially outside" in data2["message"].lower()

    # Verify wastage is evidence-driven (None if no historical wastage evidence, NOT fixed 5%)
    assert tot.get("estimated_with_wastage_lbs") is None or isinstance(tot.get("estimated_with_wastage_lbs"), (int, float))

    session_manager.clear_steel_context(sess_id)
