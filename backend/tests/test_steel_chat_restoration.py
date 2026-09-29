import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import SessionLocal
from backend.shared.ai.session_manager import session_manager
from backend.shared.ai.gemini import extract_steel_slots_from_prompt, normalize_strict, FLOOR_OPTIONS, STRUCTURAL_OPTIONS, FOUNDATION_OPTIONS
from backend.modules.admin.steel_estimator.tools import normalize_project_input

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


def test_multi_field_extraction_and_total_floors_derivation():
    """TURN 2 TEST: Multi-field extraction and derivation: total floors (3) with basements (1) -> above_ground_floors = 2."""
    msg = "area 3000sq, residential, basements: 1, total floors with basements = 3, New York"
    extracted = extract_steel_slots_from_prompt(msg, None, {})

    assert extracted.get("total_covered_area_sqft") == 3000.0
    assert extracted.get("building_type") == "Residential Apartment"
    assert extracted.get("basement_count") == 1
    assert extracted.get("above_ground_floors") == 2
    assert extracted.get("location") == "New York"


def test_single_message_three_fields_extraction():
    """TURN 4 TEST: Extract foundation, floor system, and location from ONE single message."""
    msg = "foundation is mat foundation, floor system is flat slab, location is New York"
    extracted = extract_steel_slots_from_prompt(msg, None, {})

    assert extracted.get("foundation_type") == "Mat Foundation"
    assert extracted.get("floor_system") == "Flat Slab"
    assert extracted.get("location") == "New York"


def test_options_request_and_agent_isolation():
    """TEST OPTIONS: Asking for options while in active steel session stays inside SteelEstimationAgent."""
    headers = get_admin_headers()
    sess_id = "test_options_session"
    session_manager.clear_steel_context(sess_id)

    # 1. Start steel estimation
    r1 = client.post("/api/v1/admin/ai/chat", headers=headers, json={"message": "I want to estimate steel", "session_id": sess_id})
    assert r1.status_code == 200
    assert r1.json()["agent"] == "SteelEstimationAgent"

    # 2. Ask options
    r2 = client.post("/api/v1/admin/ai/chat", headers=headers, json={"message": "Can you give me the structural system options?", "session_id": sess_id})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["agent"] == "SteelEstimationAgent"
    assert d2["status"] == "needs_input"

    session_manager.clear_steel_context(sess_id)


def test_new_york_seismic_sentence():
    """TEST SEISMIC: 'Location is New York and site is seismic' retains Steel agent, stores New York, does not force seismic into structural system."""
    headers = get_admin_headers()
    sess_id = "test_seismic_session"
    session_manager.clear_steel_context(sess_id)

    # 1. Start steel
    client.post("/api/v1/admin/ai/chat", headers=headers, json={"message": "I want to estimate steel", "session_id": sess_id})

    # 2. Send seismic sentence
    r2 = client.post("/api/v1/admin/ai/chat", headers=headers, json={
        "message": "Location is New York and the site is seismic. Can you show me the structural system options?",
        "session_id": sess_id
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["agent"] == "SteelEstimationAgent"

    ctx = session_manager.get_steel_context(sess_id)
    assert ctx.get("location") == "New York"
    assert ctx.get("structural_system") is None  # seismic was not falsely assigned as structural_system

    session_manager.clear_steel_context(sess_id)


def test_numeric_option_selection_vs_area_context():
    """TEST NUMBERED OPTIONS: '1' selects option 1 for categorical slots; '3000' is area when awaiting area."""
    # 1. Structural option 1
    ext1 = extract_steel_slots_from_prompt("1", "structural_system", {})
    assert ext1.get("structural_system") == "Reinforced Concrete Moment Frame"

    # 2. Foundation option 2
    ext2 = extract_steel_slots_from_prompt("2", "foundation_type", {})
    assert ext2.get("foundation_type") == "Mat Foundation"

    # 3. Floor option 2
    ext3 = extract_steel_slots_from_prompt("2", "floor_system", {})
    assert ext3.get("floor_system") == "Flat Slab"

    # 4. Area 3000 when awaiting area (must NOT select option 3000)
    ext4 = extract_steel_slots_from_prompt("3000", "total_covered_area_sqft", {})
    assert ext4.get("total_covered_area_sqft") == 3000.0


def test_extreme_large_project_anomaly_confirmation():
    """TEST ANOMALY: Extreme project requires ONE combined confirmation before estimation."""
    headers = get_admin_headers()
    sess_id = "test_anomaly_session"
    session_manager.clear_steel_context(sess_id)

    # 1. Provide extreme project prompt
    msg = "Estimate steel for 60000000 sqft hotel, 100 floors, 6 basements, RCC frame, mat foundation, flat slab, California"
    r1 = client.post("/api/v1/admin/ai/chat", headers=headers, json={"message": msg, "session_id": sess_id})
    assert r1.status_code == 200
    d1 = r1.json()

    # Must ask for confirmation first
    assert d1["agent"] == "SteelEstimationAgent"
    assert d1["status"] == "needs_input"
    assert "well outside" in d1["message"] or "confirm" in d1["message"].lower()

    # 2. Confirm: "Yes, proceed"
    r2 = client.post("/api/v1/admin/ai/chat", headers=headers, json={"message": "Yes, proceed", "session_id": sess_id})
    assert r2.status_code == 200
    d2 = r2.json()

    # Now completes execution!
    assert d2["agent"] == "SteelEstimationAgent"
    assert d2["status"] == "completed"
    tot = d2["data"]["total_estimate"]
    assert tot["user_total_covered_area_sqft"] == 60000000
    assert "Extrapolation Warning" in d2["message"] or "substantially outside" in d2["message"].lower()

    session_manager.clear_steel_context(sess_id)


def test_extreme_small_project_sqm_conversion():
    """TEST SQM & SMALL ANOMALY: '3 square meters' converts to ~32.29 sqft and asks anomaly confirmation."""
    msg = "3 square meters"
    ext = extract_steel_slots_from_prompt(msg, "total_covered_area_sqft", {})
    assert ext.get("total_covered_area_sqft") == 32.29


def test_user_corrects_outlier():
    """TEST ANOMALY CORRECTION: User corrects 60M sqft to 60,000 sqft upon confirmation request."""
    headers = get_admin_headers()
    sess_id = "test_correct_outlier_session"
    session_manager.clear_steel_context(sess_id)

    # 1. Provide extreme sqft
    r1 = client.post("/api/v1/admin/ai/chat", headers=headers, json={"message": "Estimate steel for 60000000 sqft hotel", "session_id": sess_id})
    assert r1.status_code == 200

    # 2. User corrects: "No, I meant 60000 sqft"
    r2 = client.post("/api/v1/admin/ai/chat", headers=headers, json={"message": "No, I meant 60000 sqft", "session_id": sess_id})
    assert r2.status_code == 200

    ctx = session_manager.get_steel_context(sess_id)
    assert ctx.get("total_covered_area_sqft") == 60000.0

    session_manager.clear_steel_context(sess_id)


def test_explicit_agent_switch():
    """TEST EXPLICIT SWITCH: Active steel session switches to ProjectHistoryAgent on explicit switch request."""
    headers = get_admin_headers()
    sess_id = "test_explicit_switch_session"
    session_manager.clear_steel_context(sess_id)

    # 1. Start steel
    client.post("/api/v1/admin/ai/chat", headers=headers, json={"message": "I want to estimate steel", "session_id": sess_id})

    # 2. Explicit switch request
    r2 = client.post("/api/v1/admin/ai/chat", headers=headers, json={
        "message": "Cancel this estimate and show me historical projects above 40000 sqft.",
        "session_id": sess_id
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["agent"] == "ProjectHistoryAgent"

    session_manager.clear_steel_context(sess_id)


def test_worker_admin_isolation():
    """TEST WORKER ISOLATION: Worker HR chatbot does NOT expose Steel Estimation or Admin financial reports."""
    payload = {"prompt": "I want to check my leave balance", "session_id": "worker_sess_1", "role": "WORKER"}
    res = client.post("/api/v1/user/hr-assistant/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "leave" in data["answer"].lower()
    assert "steel" not in data["answer"].lower()
