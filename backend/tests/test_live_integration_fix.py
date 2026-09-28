import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.core.database import Base, get_db
from backend.db.models import User, HistoricalProject, HistoricalProjectLevel, HistoricalSteelComponent
from backend.db.historical_seed import seed_historical_data
from backend.core.security import create_access_token, get_password_hash


from sqlalchemy.pool import StaticPool

from backend.core.deps import get_current_user

@pytest.fixture
def live_test_env():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 1. Seed admin user in db
    db = TestingSessionLocal()
    admin_user = User(
        email="admin_test@buildora.com",
        full_name="Admin Tester",
        role="ADMIN",
        password_hash=get_password_hash("admin123"),
    )
    db.add(admin_user)
    db.commit()

    # 2. Seed historical dataset
    seed_historical_data(db)
    admin_id = admin_user.id
    db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_get_current_user():
        session = TestingSessionLocal()
        try:
            u = session.query(User).filter(User.id == admin_id).first()
            return u
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)

    token = create_access_token(admin_id, "ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    yield client, headers, TestingSessionLocal

    app.dependency_overrides.clear()


def test_historical_seeding_counts(live_test_env):
    client, headers, TestingSessionLocal = live_test_env
    db = TestingSessionLocal()
    p_count = db.query(HistoricalProject).count()
    l_count = db.query(HistoricalProjectLevel).count()
    c_count = db.query(HistoricalSteelComponent).count()
    db.close()

    assert p_count == 22, f"Expected 22 HistoricalProjects, got {p_count}"
    assert l_count == 24, f"Expected 24 HistoricalProjectLevels, got {l_count}"
    assert c_count == 54, f"Expected 54 HistoricalSteelComponents, got {c_count}"


def test_admin_ai_chat_end_to_end_8_slot_flow(live_test_env):
    client, headers, TestingSessionLocal = live_test_env
    sess_id = "test_live_slot_flow_sess_1"

    # Step 1: Initial vague message
    res1 = client.post(
        "/api/v1/admin/ai/chat",
        headers=headers,
        json={"message": "I want to estimate steel for a new building.", "session_id": sess_id},
    )
    assert res1.status_code == 200, f"res1 failed with {res1.status_code}: {res1.text}"
    data1 = res1.json()
    assert data1["intent"] == "steel_estimation"
    assert data1["status"] == "needs_input"

    # Step 2: Provide area, building type, floors
    res2 = client.post(
        "/api/v1/admin/ai/chat",
        headers=headers,
        json={
            "message": "It is a 50,000 sqft Commercial Office with 4 floors and no basement in Austin, Texas.",
            "session_id": sess_id,
        },
    )
    assert res2.status_code == 200, f"res2 failed with {res2.status_code}: {res2.text}"
    data2 = res2.json()
    assert data2["status"] == "needs_input"

    # Step 3: Provide structural system, foundation, floor system
    with patch("backend.modules.admin.steel_estimator.final_estimation.get_market_steel_price") as mock_tavily:
        mock_tavily.return_value = {"market_price_per_ton": 980.0, "source": "Tavily Mock", "retrieval_date": "2026-09-28"}

        res3 = client.post(
            "/api/v1/admin/ai/chat",
            headers=headers,
            json={
                "message": "Use Reinforced Concrete Moment Frame, Mat Foundation, and Beam & Slab.",
                "session_id": sess_id,
            },
        )
        assert res3.status_code == 200, f"res3 failed with {res3.status_code}: {res3.text}"
        data3 = res3.json()

        # Should complete slot filling and execute Changes 3-5 pipeline
        assert data3["status"] == "completed"
        assert "data" in data3
        payload = data3["data"]
        assert payload["status"] in ("ok", "limited_evidence")

        # Verify Change 3-5 integration properties
        assert "total_estimate" in payload
        assert "confidence" in payload
        assert "market_price" in payload
        assert "material_cost" in payload
        assert payload["total_estimate"]["estimated_net_lbs"] > 0
        assert payload["total_estimate"]["estimated_net_us_tons"] > 0
        assert payload["confidence"]["label"] in ("HIGH", "MODERATE", "LOW")


def test_slot_correction_in_active_session(live_test_env):
    client, headers, TestingSessionLocal = live_test_env
    sess_id = "test_slot_correction_sess_2"

    # Send 7 fields, leaving floor_system missing
    res1 = client.post(
        "/api/v1/admin/ai/chat",
        headers=headers,
        json={
            "message": "50000 sqft Commercial Office 4 floors 0 basements Austin, Texas Reinforced Concrete Moment Frame Mat Foundation",
            "session_id": sess_id,
        },
    )
    assert res1.json()["status"] == "needs_input"

    # User corrects foundation_type and supplies floor_system
    with patch("backend.modules.admin.steel_estimator.final_estimation.get_market_steel_price") as mock_tavily:
        mock_tavily.return_value = {"market_price_per_ton": 980.0, "source": "Tavily Mock"}

        res = client.post(
            "/api/v1/admin/ai/chat",
            headers=headers,
            json={"message": "Actually use Spread Footing and Beam & Slab.", "session_id": sess_id},
        )
        assert res.status_code == 200, f"Got status {res.status_code}: {res.text}"
        data = res.json()
        assert data["status"] == "completed"
        assert data["data"]["project_inputs"]["foundation_type"] in ("Spread Footing", "Spread Footings")
