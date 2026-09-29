import json
from backend.core.database import SessionLocal
from backend.shared.ai.gemini import extract_steel_slots_from_prompt
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
from backend.main import app
from fastapi.testclient import TestClient
from backend.core.security import create_access_token
from backend.db.models import User

msg = "Estimate steel for 50000 sqft residential building, 5 floors, 1 basement, RCC frame, mat foundation, beam and slab, Los Angeles CA"

# 1. Slot extraction
extracted = extract_steel_slots_from_prompt(msg, None, {})
norm_inputs = normalize_project_input(extracted)
print("Extracted slots:", extracted)
print("Normalized inputs:", norm_inputs)

db = SessionLocal()

# 2. Direct Service Call with extracted & normalized inputs
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

agg = aggregate_steel_estimate(db, norm_inputs, components, similarity_result=hist_data, fetch_market_price=False)
tot = agg["total_estimate"]
conf = agg["confidence"]

print("\n=== DIRECT SERVICE WITH EXTRACTED SLOTS ===")
print("Net lbs:", tot.get("estimated_net_lbs"))
print("Net tons:", tot.get("estimated_net_us_tons"))
print("Confidence:", conf.get("display_score"), conf.get("label"))

# 3. Chat Endpoint Call
admin_user = db.query(User).filter(User.role == "ADMIN").first()
admin_id = admin_user.id if admin_user else 1
db.close()

token = create_access_token(subject=str(admin_id), role="ADMIN")
client = TestClient(app)

res = client.post(
    "/api/v1/admin/ai/chat",
    headers={"Authorization": f"Bearer {token}"},
    json={"message": msg}
)

chat_data = res.json()
p_data = chat_data.get("data", {}).get("total_estimate", {})
c_data = chat_data.get("data", {}).get("confidence", {})

print("\n=== CHAT ENDPOINT RESULT ===")
print("Chat Net lbs:", p_data.get("estimated_net_lbs"))
print("Chat Net tons:", p_data.get("estimated_net_us_tons"))
print("Chat Confidence:", c_data.get("display_score"), c_data.get("label"))

print("\n=== ARE DIRECT SERVICE AND CHAT 100% IDENTICAL? ===")
is_identical = (tot.get("estimated_net_lbs") == p_data.get("estimated_net_lbs")) and (conf.get("display_score") == c_data.get("display_score"))
print("IDENTICAL:", is_identical)
