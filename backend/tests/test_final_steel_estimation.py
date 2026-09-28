import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, HistoricalProject
from backend.modules.admin.steel_estimator.final_estimation import (
    estimate_whole_project_steel,
    calculate_evidence_confidence,
    normalize_market_price,
    evaluate_steel_material_cost,
    MAX_TOTAL_EVIDENCE_PROJECTS,
)
from backend.modules.admin.steel_estimator.tools import aggregate_steel_estimate, find_similar_historical_projects
from backend.modules.admin.steel_estimator.service import calculate_steel_estimation
from backend.modules.admin.steel_estimator.schemas import SteelEstimateRequestSchema


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Seed test projects
    p1 = HistoricalProject(
        project_key="P001",
        project_title="Project Alpha",
        building_type="Commercial",
        location="Austin, Texas",
        total_covered_area_sqft=100000.0,
        total_rebar_net_lbs=500000.0,
        total_rebar_with_wastage_lbs=525000.0,
        data_quality="SOURCE_VERIFIED",
    )
    p2 = HistoricalProject(
        project_key="P002",
        project_title="Project Beta",
        building_type="Commercial",
        location="Dallas, Texas",
        total_covered_area_sqft=80000.0,
        total_rebar_net_lbs=360000.0,
        total_rebar_with_wastage_lbs=378000.0,
        data_quality="SOURCE_VERIFIED",
    )
    p3 = HistoricalProject(
        project_key="P003",
        project_title="Project Gamma",
        building_type="Commercial",
        location="Houston, Texas",
        total_covered_area_sqft=120000.0,
        total_rebar_net_lbs=660000.0,
        total_rebar_with_wastage_lbs=None, # Missing wastage
        data_quality="SOURCE_VERIFIED",
    )
    p22 = HistoricalProject(
        project_key="P022",
        project_title="Austin Commercial Tower B",
        building_type="Commercial",
        location="Austin, Texas",
        total_covered_area_sqft=500000.0,
        total_rebar_net_lbs=2500000.0,
        data_quality="REFERENCE", # REFERENCE excluded
    )
    db.add_all([p1, p2, p3, p22])
    db.commit()

    yield db
    db.close()


# ------------------------------------------------------------------------------
# 1. Whole-Project Net & Wastage Quantity Tests
# ------------------------------------------------------------------------------
def test_estimate_whole_project_steel_weighted_ratio():
    mock_similarity = {
        "candidates": [
            {
                "project_key": "P001",
                "project_title": "Project Alpha",
                "ranking_score": 0.8,
                "similarity_score": 0.9,
                "coverage_score": 0.88,
                "total_covered_area_sqft": 100000.0,
                "data_quality": "SOURCE_VERIFIED",
                "evidence": {"project_total": {"total_rebar_net_lbs": 500000.0, "total_rebar_with_wastage_lbs": 525000.0}},
            },
            {
                "project_key": "P002",
                "project_title": "Project Beta",
                "ranking_score": 0.6,
                "similarity_score": 0.7,
                "coverage_score": 0.85,
                "total_covered_area_sqft": 80000.0,
                "data_quality": "SOURCE_VERIFIED",
                "evidence": {"project_total": {"total_rebar_net_lbs": 360000.0, "total_rebar_with_wastage_lbs": 378000.0}},
            },
        ]
    }
    user_inputs = {"total_covered_area_sqft": 50000.0}

    # Ratio P001 = 500000 / 100000 = 5.0 lbs/sqft
    # Ratio P002 = 360000 / 80000 = 4.5 lbs/sqft
    # Weighted Ratio = (0.8 * 5.0 + 0.6 * 4.5) / (0.8 + 0.6) = (4.0 + 2.7) / 1.4 = 6.7 / 1.4 = 4.785714 lbs/sqft
    # Net lbs = 4.785714 * 50000 = 239285.71 lbs
    # US Short Tons = 239285.71 / 2000 = 119.64 tons

    res = estimate_whole_project_steel(mock_similarity, user_inputs)

    assert res["status"] == "ok"
    assert res["historical_projects_used"] == 2
    assert res["weighted_net_ratio"] == 4.785714
    assert res["estimated_net_lbs"] == 239285.7
    assert res["estimated_net_us_tons"] == 119.64


def test_area_applied_exactly_once_no_floor_multiplication():
    mock_similarity = {
        "candidates": [
            {
                "project_key": "P001",
                "project_title": "Project Alpha",
                "ranking_score": 1.0,
                "similarity_score": 1.0,
                "coverage_score": 1.0,
                "total_covered_area_sqft": 100000.0,
                "data_quality": "SOURCE_VERIFIED",
                "evidence": {"project_total": {"total_rebar_net_lbs": 500000.0}}, # ratio = 5.0
            }
        ]
    }
    # 50,000 sqft TOTAL area with 10 floors must still use 50,000 sqft total (NOT 500,000 sqft!)
    user_inputs = {"total_covered_area_sqft": 50000.0, "above_ground_floors": 10}
    res = estimate_whole_project_steel(mock_similarity, user_inputs)

    assert res["estimated_net_lbs"] == 250000.0  # 50000 * 5.0
    assert res["estimated_net_us_tons"] == 125.0


def test_reference_project_p022_excluded():
    mock_similarity = {
        "candidates": [
            {
                "project_key": "P022",
                "project_title": "Austin Commercial Tower B",
                "ranking_score": 0.99,
                "similarity_score": 0.99,
                "coverage_score": 1.0,
                "total_covered_area_sqft": 500000.0,
                "data_quality": "REFERENCE",
                "evidence": {"project_total": {"total_rebar_net_lbs": 2500000.0}},
            }
        ]
    }
    user_inputs = {"total_covered_area_sqft": 50000.0}
    res = estimate_whole_project_steel(mock_similarity, user_inputs)

    assert res["status"] == "insufficient_historical_data"
    assert res["historical_projects_used"] == 0


def test_wastage_quantity_independent_from_net():
    mock_similarity = {
        "candidates": [
            {
                "project_key": "P001",
                "project_title": "Project Alpha",
                "ranking_score": 1.0,
                "similarity_score": 1.0,
                "coverage_score": 1.0,
                "total_covered_area_sqft": 100000.0,
                "data_quality": "SOURCE_VERIFIED",
                "evidence": {"project_total": {"total_rebar_net_lbs": 500000.0, "total_rebar_with_wastage_lbs": 530000.0}},
            },
            {
                "project_key": "P003",
                "project_title": "Project Gamma",
                "ranking_score": 1.0,
                "similarity_score": 1.0,
                "coverage_score": 1.0,
                "total_covered_area_sqft": 100000.0,
                "data_quality": "SOURCE_VERIFIED",
                "evidence": {"project_total": {"total_rebar_net_lbs": 500000.0, "total_rebar_with_wastage_lbs": None}}, # Missing
            },
        ]
    }
    user_inputs = {"total_covered_area_sqft": 10000.0}
    res = estimate_whole_project_steel(mock_similarity, user_inputs)

    assert res["estimated_net_lbs"] == 50000.0
    # Wastage uses only P001 ratio 5.3 lbs/sqft
    assert res["estimated_with_wastage_lbs"] == 53000.0
    assert len(res["wastage_samples"]) == 1


# ------------------------------------------------------------------------------
# 2. Evidence Confidence Tests
# ------------------------------------------------------------------------------
def test_confidence_formula_controlled_values():
    samples = [
        {"similarity_score": 0.80, "coverage_score": 0.90, "ranking_score": 0.72, "historical_net_ratio": 5.0},
        {"similarity_score": 0.80, "coverage_score": 0.90, "ranking_score": 0.72, "historical_net_ratio": 5.0},
        {"similarity_score": 0.80, "coverage_score": 0.90, "ranking_score": 0.72, "historical_net_ratio": 5.0},
    ]
    # sample_count = 3 -> sample_strength = 3/5 = 0.60
    # similarity_strength = 0.80
    # coverage_strength = 0.90
    # ratios identical -> CV = 0 -> consistency_strength = 1.0
    # raw_confidence = 0.30(0.80) + 0.25(0.90) + 0.20(0.60) + 0.25(1.0) = 0.24 + 0.225 + 0.12 + 0.25 = 0.835
    res = calculate_evidence_confidence(samples)

    assert res["status"] == "ok"
    assert res["evidence_confidence_score"] == 0.835
    assert res["display_score"] == 84
    assert res["label"] == "HIGH"


def test_confidence_small_sample_caps():
    # 1 sample cap = 0.45
    s1 = [{"similarity_score": 1.0, "coverage_score": 1.0, "ranking_score": 1.0, "historical_net_ratio": 5.0}]
    c1 = calculate_evidence_confidence(s1)
    assert c1["evidence_confidence_score"] <= 0.45
    assert c1["label"] == "LOW"

    # 2 sample cap = 0.65
    s2 = s1 + [{"similarity_score": 1.0, "coverage_score": 1.0, "ranking_score": 1.0, "historical_net_ratio": 5.0}]
    c2 = calculate_evidence_confidence(s2)
    assert c2["evidence_confidence_score"] <= 0.65
    assert c2["label"] == "MODERATE"


def test_zero_samples_confidence():
    res = calculate_evidence_confidence([])
    assert res["status"] == "UNAVAILABLE"
    assert res["label"] == "UNAVAILABLE"


# ------------------------------------------------------------------------------
# 3. Market Price Normalization & Cost Tests
# ------------------------------------------------------------------------------
@patch("backend.modules.admin.steel_estimator.final_estimation.get_market_steel_price")
def test_normalize_market_price_success(mock_tavily):
    mock_tavily.return_value = {
        "market_price_per_ton": 950.0,
        "source": "Tavily Mock",
        "retrieval_date": "2026-09-28",
        "query_used": "Grade 60 rebar price",
    }
    res = normalize_market_price("Texas, US")
    assert res["status"] == "ok"
    assert res["normalized_price_usd_per_us_ton"] == 950.0
    assert res["currency"] == "USD"
    assert res["raw_unit"] == "US short ton"


@patch("backend.modules.admin.steel_estimator.final_estimation.get_market_steel_price")
def test_normalize_market_price_failure(mock_tavily):
    mock_tavily.return_value = {"market_price_per_ton": None, "source": "Failed"}
    res = normalize_market_price("Texas, US")
    assert res["status"] == "unavailable"
    assert res["normalized_price_usd_per_us_ton"] is None


def test_evaluate_steel_material_cost_basis():
    total_est = {
        "estimated_net_us_tons": 100.0,
        "estimated_with_wastage_us_tons": 105.0,
    }
    market_price = {"status": "ok", "normalized_price_usd_per_us_ton": 1000.0}

    res = evaluate_steel_material_cost(total_est, market_price)
    assert res["status"] == "ok"
    assert res["net_material_cost_usd"] == 100000.0
    assert res["with_wastage_material_cost_usd"] == 105000.0
    assert res["final_material_cost_usd"] == 105000.0
    assert res["cost_basis"] == "historical_with_wastage_quantity"


def test_evaluate_steel_material_cost_net_only_fallback():
    total_est = {
        "estimated_net_us_tons": 100.0,
        "estimated_with_wastage_us_tons": None,
    }
    market_price = {"status": "ok", "normalized_price_usd_per_us_ton": 1000.0}

    res = evaluate_steel_material_cost(total_est, market_price)
    assert res["status"] == "ok"
    assert res["final_material_cost_usd"] == 100000.0
    assert res["cost_basis"] == "net_quantity_only"


# ------------------------------------------------------------------------------
# 4. Old Logic Regression Test & Component Integration
# ------------------------------------------------------------------------------
def test_old_4_5_fallback_removed_from_service(in_memory_db):
    with patch("backend.modules.admin.steel_estimator.final_estimation.get_market_steel_price") as mock_tavily:
        mock_tavily.return_value = {"market_price_per_ton": 1000.0, "source": "Mock"}
        req = SteelEstimateRequestSchema(
            project_name="Test Project",
            project_type="Commercial",
            total_sqft=50000.0,
            location="Austin, Texas",
        )
        res = calculate_steel_estimation(in_memory_db, req)

        # Average historical ratio for seeded P001, P002, P003:
        # P001: 5.0, P002: 4.5, P003: 5.5 -> weighted ratio ~ 5.0 lbs/sqft
        # 50,000 * 5.0 = 250,000 lbs = 125 tons
        # Must NOT use 4.5 lbs/sqft static fallback!
        assert res.estimated_rebar_tons != 112.5  # 50000 * 4.5 / 2000 = 112.5
        assert res.estimated_rebar_tons > 0
