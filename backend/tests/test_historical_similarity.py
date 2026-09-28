import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.db.models import HistoricalProject, HistoricalProjectLevel, HistoricalSteelComponent
from backend.db.historical_seed import seed_historical_data
from backend.shared.ai.tools import load_source_backed_historical_projects
from backend.modules.admin.steel_estimator.historical_similarity import (
    score_area_similarity,
    score_floors_similarity,
    score_basement_similarity,
    score_categorical_similarity,
    score_location_similarity,
    evaluate_project_similarity,
    evaluate_evidence_profile,
    rank_and_build_evidence_pools,
    BUILDING_TYPE_ALIASES,
    STRUCTURAL_SYSTEM_ALIASES,
    FOUNDATION_TYPE_ALIASES,
    FLOOR_SYSTEM_ALIASES,
)
from backend.modules.admin.steel_estimator.tools import (
    find_similar_historical_projects,
    analyze_historical_steel_usage,
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


def test_area_similarity_formula():
    status, score = score_area_similarity(40000.0, 40000.0)
    assert status == "MATCHED"
    assert score == 1.0

    status, score = score_area_similarity(40000.0, 36000.0)
    assert status == "PARTIAL_MATCH"
    assert score == 0.9000

    status, score = score_area_similarity(40000.0, 20000.0)
    assert status == "PARTIAL_MATCH"
    assert score == 0.5000

    # Symmetric test
    _, score1 = score_area_similarity(40000.0, 20000.0)
    _, score2 = score_area_similarity(20000.0, 40000.0)
    assert score1 == score2

    # Missing area
    status, score = score_area_similarity(None, 40000.0)
    assert status == "UNKNOWN"
    assert score is None


def test_floors_similarity_formula():
    assert score_floors_similarity(5, 5) == ("MATCHED", 1.0)
    assert score_floors_similarity(5, 4) == ("PARTIAL_MATCH", 0.8)
    assert score_floors_similarity(5, 3) == ("PARTIAL_MATCH", 0.6)

    status, score = score_floors_similarity(None, 5)
    assert status == "UNKNOWN"
    assert score is None


def test_basement_similarity_formula():
    assert score_basement_similarity(1, 1) == ("MATCHED", 1.0)
    assert score_basement_similarity(1, 0) == ("PARTIAL_MATCH", 0.5)
    assert score_basement_similarity(2, 0) == ("MISMATCHED", 0.0)

    # NULL basement is UNKNOWN, not mismatch
    status, score = score_basement_similarity(1, None)
    assert status == "UNKNOWN"
    assert score is None


def test_categorical_matching_and_aliases():
    assert score_categorical_similarity("Commercial", "Commercial", BUILDING_TYPE_ALIASES) == ("MATCHED", 1.0)
    assert score_categorical_similarity("RCC Frame", "Reinforced Concrete Frame", STRUCTURAL_SYSTEM_ALIASES) == ("MATCHED", 1.0)
    assert score_categorical_similarity("Mat Foundation", "Raft Foundation", FOUNDATION_TYPE_ALIASES) == ("MATCHED", 1.0)
    assert score_categorical_similarity("Beam-Slab", "Beam & Slab", FLOOR_SYSTEM_ALIASES) == ("MATCHED", 1.0)
    assert score_categorical_similarity("Commercial", "Residential", BUILDING_TYPE_ALIASES) == ("MISMATCHED", 0.0)

    status, score = score_categorical_similarity("Commercial", None, BUILDING_TYPE_ALIASES)
    assert status == "UNKNOWN"
    assert score is None


def test_location_similarity_formula():
    # Same city & state
    assert score_location_similarity("Los Angeles, CA", "160 S Union Ave, Los Angeles, CA 90026") == ("MATCHED", 1.0)
    # Different city, same state
    assert score_location_similarity("Los Angeles, CA", "4212 McLaughlin Ave, Culver City, CA 90066") == ("PARTIAL_MATCH", 0.5)
    # Different state
    assert score_location_similarity("Austin, TX", "Los Angeles, CA 90026") == ("MISMATCHED", 0.0)
    # Unknown/Incomplete
    assert score_location_similarity("Unknown Location", None)[0] == "UNKNOWN"


def test_coverage_and_ranking_scores():
    user_inputs = {
        "total_covered_area_sqft": 40000.0,
        "building_type": "Commercial",
        "basement_count": 1,
        "above_ground_floors": 4,
        "structural_system": "Reinforced Concrete Frame",
        "foundation_type": "Mat Foundation",
        "floor_system": "Flat Slab",
        "location": "Los Angeles, CA",
    }

    # Candidate with complete fields
    proj_full = {
        "project_key": "P001",
        "project_title": "Full Project",
        "total_covered_area_sqft": 40000.0,
        "building_type": "Commercial",
        "basement_count": 1,
        "above_ground_floors": 4,
        "structural_system": "Reinforced Concrete Frame",
        "foundation_type": "Mat Foundation",
        "floor_system": "Flat Slab",
        "location": "Los Angeles, CA",
    }
    eval_full = evaluate_project_similarity(user_inputs, proj_full)
    assert eval_full["similarity_score"] == 1.0
    assert eval_full["coverage_score"] == 1.0
    assert eval_full["ranking_score"] == 1.0

    # Candidate with high similarity on 2 known fields, but 6 unknown fields
    proj_sparse = {
        "project_key": "P002",
        "project_title": "Sparse Project",
        "total_covered_area_sqft": 40000.0,
        "building_type": "Commercial",
        "basement_count": None,
        "above_ground_floors": None,
        "structural_system": None,
        "foundation_type": None,
        "floor_system": None,
        "location": None,
    }
    eval_sparse = evaluate_project_similarity(user_inputs, proj_sparse)
    assert eval_sparse["similarity_score"] == 1.0
    assert eval_sparse["coverage_score"] == 0.30  # (20 + 10) / 100
    assert eval_sparse["ranking_score"] == 0.30  # 1.0 * 0.30

    # Full project ranks above sparse project despite both having similarity_score 1.0
    assert eval_full["ranking_score"] > eval_sparse["ranking_score"]


def test_reference_p022_exclusion(test_db):
    projs = load_source_backed_historical_projects(test_db)
    user_inputs = {"total_covered_area_sqft": 45000.0, "building_type": "Commercial"}

    res = rank_and_build_evidence_pools(user_inputs, projs, top_k=10)
    candidate_keys = [c["project_key"] for c in res["candidates"]]
    assert "P022" not in candidate_keys, "P022 REFERENCE must be excluded from candidates."

    for pool in res["evidence_pools"].values():
        pool_keys = [item["project_key"] for item in pool]
        assert "P022" not in pool_keys, "P022 REFERENCE must be excluded from evidence pools."


def test_dataset_evidence_profiles(test_db):
    projs = load_source_backed_historical_projects(test_db)
    proj_map = {p.project_key: p for p in projs}

    # P001: project_total, foundation, ground, upper_floor
    p001 = proj_map.get("P001")
    assert p001 is not None
    ev001 = evaluate_evidence_profile(p001)
    assert ev001["project_total"]["available"] is True
    assert ev001["foundation"]["available"] is True
    assert ev001["ground"]["available"] is True
    assert ev001["upper_floor"]["available"] is True

    # P005: project_total, foundation, basement, ground, upper_floor
    p005 = proj_map.get("P005")
    assert p005 is not None
    ev005 = evaluate_evidence_profile(p005)
    assert ev005["project_total"]["available"] is True
    assert ev005["foundation"]["available"] is True
    assert ev005["basement"]["available"] is True
    assert ev005["ground"]["available"] is True
    assert ev005["upper_floor"]["available"] is True

    # P003: project_total only
    p003 = proj_map.get("P003")
    assert p003 is not None
    ev003 = evaluate_evidence_profile(p003)
    assert ev003["project_total"]["available"] is True
    assert ev003["foundation"]["available"] is False
    assert ev003["basement"]["available"] is False
    assert ev003["ground"]["available"] is False
    assert ev003["upper_floor"]["available"] is False

    # Roof pool is empty across historical dataset
    user_inputs = {"total_covered_area_sqft": 45000.0}
    res = rank_and_build_evidence_pools(user_inputs, projs, top_k=10)
    assert len(res["evidence_pools"]["roof"]) == 0


def test_quantity_scope_preservation(test_db):
    projs = load_source_backed_historical_projects(test_db)
    for p in projs:
        ev = evaluate_evidence_profile(p)
        for domain in ["foundation", "basement", "ground", "upper_floor", "roof"]:
            for lvl_meta in ev[domain]["levels"]:
                assert "quantity_scope" in lvl_meta
                assert lvl_meta["quantity_scope"] in ["COMPLETE_LEVEL", "PARTIAL_LEVEL", "SECTION_ONLY", "UNKNOWN"]


def test_determinism(test_db):
    inputs = {
        "total_covered_area_sqft": 45000.0,
        "building_type": "Commercial",
        "location": "Los Angeles, CA"
    }

    res1 = find_similar_historical_projects(test_db, inputs, top_k=5)
    res2 = find_similar_historical_projects(test_db, inputs, top_k=5)

    keys1 = [c["project_key"] for c in res1["candidates"]]
    keys2 = [c["project_key"] for c in res2["candidates"]]
    assert keys1 == keys2

    scores1 = [c["ranking_score"] for c in res1["candidates"]]
    scores2 = [c["ranking_score"] for c in res2["candidates"]]
    assert scores1 == scores2


def test_analyze_historical_steel_usage_descriptive(test_db):
    inputs = {"total_covered_area_sqft": 45000.0, "building_type": "Commercial"}
    similar_res = find_similar_historical_projects(test_db, inputs, top_k=5)
    analysis = analyze_historical_steel_usage(similar_res)

    assert analysis["status"] == "ok"
    assert analysis["sample_size"] > 0
    assert isinstance(analysis["average_lbs_per_sqft"], float)
    assert isinstance(analysis["median_lbs_per_sqft"], float)
    assert isinstance(analysis["min_lbs_per_sqft"], float)
    assert isinstance(analysis["max_lbs_per_sqft"], float)
    # Verify no steel total or quantity estimation formula was executed
    assert "estimated_rebar_tons" not in analysis
