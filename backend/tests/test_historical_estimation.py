import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.db.historical_seed import seed_historical_data
from backend.shared.ai.tools import load_source_backed_historical_projects
from backend.modules.admin.steel_estimator.historical_similarity import rank_and_build_evidence_pools
from backend.modules.admin.steel_estimator.historical_estimation import (
    compute_weighted_ratio,
    estimate_foundation_steel,
    estimate_basement_steel,
    estimate_ground_floor_steel,
    estimate_upper_floor_steel,
    estimate_roof_steel,
)
from backend.modules.admin.steel_estimator.tools import (
    calculate_foundation_steel,
    calculate_basement_steel,
    calculate_ground_floor_steel,
    calculate_upper_floor_steel,
    calculate_roof_steel,
)


@pytest.fixture(scope="module")
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed historical dataset
    seed_historical_data(session)

    yield session

    session.close()


def test_ranking_weighted_ratio_math():
    samples = [
        {"ranking_score": 0.8, "historical_component_net_ratio": 1.0},
        {"ranking_score": 0.2, "historical_component_net_ratio": 2.0},
    ]
    weighted_ratio, sum_w = compute_weighted_ratio(samples, "historical_component_net_ratio")
    assert sum_w == 1.0
    assert weighted_ratio == 1.2


def test_zero_ranking_score_weights():
    samples = [
        {"ranking_score": 0.0, "historical_component_net_ratio": 1.5},
    ]
    weighted_ratio, sum_w = compute_weighted_ratio(samples, "historical_component_net_ratio")
    assert weighted_ratio is None
    assert sum_w == 0.0


def test_foundation_steel_estimation_rules(test_db):
    user_inputs = {
        "total_covered_area_sqft": 40000.0,
        "building_type": "Commercial",
        "structural_system": "Reinforced Concrete Frame",
        "foundation_type": "Mat Foundation",
        "location": "Los Angeles, CA",
    }
    sim_res = rank_and_build_evidence_pools(user_inputs, load_source_backed_historical_projects(test_db))

    res = estimate_foundation_steel(sim_res, user_inputs)
    assert res["status"] in ["ok", "limited_evidence"]
    assert res["component"] == "foundation"
    assert res["user_total_covered_area_sqft"] == 40000.0
    assert res["estimated_net_lbs"] > 0
    assert res["estimated_net_us_tons"] == round(res["estimated_net_lbs"] / 2000.0, 2)

    # Check supporting evidence preserved
    assert len(res["supporting_evidence"]) > 0
    for supp in res["supporting_evidence"]:
        assert supp["usable_for_point_estimate"] is False
        assert "exclusion_reason" in supp


def test_basement_steel_estimation_rules(test_db):
    # Case A: User specifies 0 basements
    user_zero_b = {"total_covered_area_sqft": 40000.0, "basement_count": 0}
    sim_zero = rank_and_build_evidence_pools(user_zero_b, load_source_backed_historical_projects(test_db))
    res_zero = estimate_basement_steel(sim_zero, user_zero_b)
    assert res_zero["status"] == "not_applicable"
    assert res_zero["estimated_net_lbs"] == 0.0
    assert res_zero["estimated_net_us_tons"] == 0.0

    # Case B: User specifies 1 basement
    user_one_b = {
        "total_covered_area_sqft": 40000.0,
        "basement_count": 1,
        "building_type": "Commercial",
        "location": "Los Angeles, CA",
    }
    sim_one = rank_and_build_evidence_pools(user_one_b, load_source_backed_historical_projects(test_db))
    res_one = estimate_basement_steel(sim_one, user_one_b)
    assert res_one["status"] in ["ok", "limited_evidence"]
    assert res_one["estimated_net_lbs"] > 0
    assert res_one["estimated_net_us_tons"] == round(res_one["estimated_net_lbs"] / 2000.0, 2)


def test_ground_steel_estimation_rules(test_db):
    user_inputs = {
        "total_covered_area_sqft": 40000.0,
        "building_type": "Commercial",
        "location": "Los Angeles, CA",
    }
    sim_res = rank_and_build_evidence_pools(user_inputs, load_source_backed_historical_projects(test_db))
    res = estimate_ground_floor_steel(sim_res, user_inputs)
    assert res["status"] in ["ok", "limited_evidence"]
    assert res["component"] == "ground_floor"
    assert res["estimated_net_lbs"] > 0
    assert res["estimated_net_us_tons"] == round(res["estimated_net_lbs"] / 2000.0, 2)


def test_upper_floor_steel_estimation_rules(test_db):
    # Case A: Single-story building (above_ground_floors = 1)
    user_single_story = {"total_covered_area_sqft": 40000.0, "above_ground_floors": 1}
    sim_single = rank_and_build_evidence_pools(user_single_story, load_source_backed_historical_projects(test_db))
    res_single = estimate_upper_floor_steel(sim_single, user_single_story)
    assert res_single["status"] == "not_applicable"
    assert res_single["estimated_net_lbs"] == 0.0

    # Case B: Multi-story building
    user_multi = {
        "total_covered_area_sqft": 40000.0,
        "above_ground_floors": 3,
        "building_type": "Commercial",
        "location": "Los Angeles, CA",
    }
    sim_multi = rank_and_build_evidence_pools(user_multi, load_source_backed_historical_projects(test_db))
    res_multi = estimate_upper_floor_steel(sim_multi, user_multi)
    # Complete upper-floor category coverage in historical dataset for multi-story is incomplete
    assert res_multi["status"] in ["insufficient_component_data", "limited_evidence", "ok"]


def test_roof_steel_estimation_rules(test_db):
    user_inputs = {"total_covered_area_sqft": 40000.0}
    sim_res = rank_and_build_evidence_pools(user_inputs, load_source_backed_historical_projects(test_db))
    res = estimate_roof_steel(sim_res, user_inputs)

    assert res["status"] == "insufficient_component_data"
    assert res["component"] == "roof"
    assert res["estimated_net_lbs"] is None
    assert res["estimated_net_us_tons"] is None
    assert "No isolated roof reinforcement evidence exists" in res["reason"]


def test_unit_conversion():
    lbs = 50000.0
    tons = lbs / 2000.0
    assert tons == 25.0


def test_tool_wrappers_integration(test_db):
    user_inputs = {
        "total_covered_area_sqft": 45000.0,
        "building_type": "Commercial",
        "basement_count": 1,
        "above_ground_floors": 4,
        "structural_system": "Reinforced Concrete Frame",
        "foundation_type": "Mat Foundation",
        "floor_system": "Flat Slab",
        "location": "Los Angeles, CA",
    }

    found_res = calculate_foundation_steel(test_db, user_inputs)
    assert found_res["status"] in ["ok", "limited_evidence"]

    base_res = calculate_basement_steel(test_db, user_inputs)
    assert base_res["status"] in ["ok", "limited_evidence"]

    ground_res = calculate_ground_floor_steel(test_db, user_inputs)
    assert ground_res["status"] in ["ok", "limited_evidence"]

    upper_res = calculate_upper_floor_steel(test_db, user_inputs)
    assert upper_res["status"] in ["insufficient_component_data", "limited_evidence", "ok"]

    roof_res = calculate_roof_steel(test_db, user_inputs)
    assert roof_res["status"] == "insufficient_component_data"
