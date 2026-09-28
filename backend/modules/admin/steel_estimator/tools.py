import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.shared.ai.tools import query_historical_projects_db
from backend.shared.ai.tavily import get_market_steel_price
from backend.modules.admin.steel_estimator.service import calculate_steel_estimation
from backend.modules.admin.steel_estimator.schemas import SteelEstimateRequestSchema

logger = logging.getLogger("buildora.steel_estimator.tools")


def normalize_project_input(raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes extracted project inputs without changing core numerical values.
    Ensures total_covered_area_sqft, building_type, basement_count, above_ground_floors,
    structural_system, foundation_type, floor_system, location, and fixed steel_grade Grade 60.
    """
    normalized = dict(raw_inputs)

    # 1. Total Covered Area
    area = normalized.get("total_covered_area_sqft") or normalized.get("covered_area_sqft")
    if area is not None:
        try:
            normalized["total_covered_area_sqft"] = float(area)
        except (ValueError, TypeError):
            pass

    # 2. Building Type
    btype = normalized.get("building_type")
    if btype:
        normalized["building_type"] = str(btype).strip().title()

    # 3. Basement Count
    b_count = normalized.get("basement_count")
    if b_count is not None:
        try:
            normalized["basement_count"] = max(0, int(b_count))
        except (ValueError, TypeError):
            pass

    # 4. Above Ground Floors
    ag_floors = normalized.get("above_ground_floors") or normalized.get("floors")
    if ag_floors is not None:
        try:
            normalized["above_ground_floors"] = max(1, int(ag_floors))
        except (ValueError, TypeError):
            pass

    # 5. Fixed System Rule: Grade 60
    normalized["steel_grade"] = "Grade 60"

    return normalized


def validate_project_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates project inputs prior to estimation execution.
    Returns structured validation status with missing fields or errors.
    """
    area = inputs.get("total_covered_area_sqft")
    btype = inputs.get("building_type")
    b_count = inputs.get("basement_count")
    ag_floors = inputs.get("above_ground_floors")
    struct = inputs.get("structural_system")
    found = inputs.get("foundation_type")
    fl_sys = inputs.get("floor_system")
    loc = inputs.get("location")

    required_map = {
        "total_covered_area_sqft": area,
        "building_type": btype,
        "basement_count": b_count,
        "above_ground_floors": ag_floors,
        "structural_system": struct,
        "foundation_type": found,
        "floor_system": fl_sys,
        "location": loc,
    }

    missing = [k for k, v in required_map.items() if v is None]
    errors = []

    if area is not None and area <= 0:
        errors.append("total_covered_area_sqft must be greater than 0.")
    if b_count is not None and b_count < 0:
        errors.append("basement_count cannot be negative.")
    if ag_floors is not None and ag_floors < 1:
        errors.append("above_ground_floors must be at least 1 (Ground floor minimum).")

    is_valid = len(missing) == 0 and len(errors) == 0

    return {
        "is_valid": is_valid,
        "missing_fields": missing,
        "errors": errors,
        "validated_inputs": inputs if is_valid else None
    }


from backend.shared.ai.tools import load_source_backed_historical_projects, query_historical_projects_db
from backend.modules.admin.steel_estimator.historical_similarity import rank_and_build_evidence_pools

def find_similar_historical_projects(db: Session, inputs: Dict[str, Any], top_k: int = 5) -> Dict[str, Any]:
    """
    Deterministically ranks historical structural projects across all 8 inputs
    and returns structured candidates, match feature details, and evidence pools.
    """
    normalized = normalize_project_input(inputs)
    historical_projects = load_source_backed_historical_projects(db)
    result = rank_and_build_evidence_pools(normalized, historical_projects, top_k=top_k)
    return result


def analyze_historical_steel_usage(historical_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes historical steel usage ratios (lbs/sqft) truthfully from matched candidates.
    Returns descriptive statistics ONLY (min, max, mean, median, sample size).
    Does NOT calculate final user steel quantity or use fake fallbacks.
    """
    candidates = historical_data.get("candidates", [])
    if not candidates and "projects" in historical_data:
        # Compatibility fallback for raw project list
        candidates = historical_data.get("projects", [])

    ratios = []
    ratio_details = []
    for c in candidates:
        ev = c.get("evidence", {}).get("project_total", {})
        ratio = ev.get("overall_rebar_ratio_lbs_per_sqft")
        pkey = c.get("project_key") or c.get("name")
        if ratio is not None and ratio > 0:
            ratios.append(ratio)
            ratio_details.append({"project_key": pkey, "ratio_lbs_per_sqft": round(ratio, 3)})
        else:
            rebar_lbs = ev.get("total_rebar_net_lbs") or c.get("total_rebar_net_lbs")
            sqft = ev.get("total_covered_area_sqft") or c.get("sqft") or c.get("total_covered_area_sqft")
            if rebar_lbs and sqft and sqft > 0:
                calc_ratio = round(rebar_lbs / sqft, 3)
                ratios.append(calc_ratio)
                ratio_details.append({"project_key": pkey, "ratio_lbs_per_sqft": calc_ratio})

    if not ratios:
        return {
            "status": "insufficient_historical_ratio_data",
            "match_count": len(candidates),
            "sample_size": 0,
            "average_lbs_per_sqft": None,
            "median_lbs_per_sqft": None,
            "min_lbs_per_sqft": None,
            "max_lbs_per_sqft": None,
            "ratio_details": [],
            "note": "No usable historical rebar intensity ratios (lbs/sqft) available for matched candidates."
        }

    sorted_ratios = sorted(ratios)
    n = len(sorted_ratios)
    avg_ratio = round(sum(sorted_ratios) / float(n), 3)
    if n % 2 == 1:
        median_ratio = round(sorted_ratios[n // 2], 3)
    else:
        median_ratio = round((sorted_ratios[n // 2 - 1] + sorted_ratios[n // 2]) / 2.0, 3)

    return {
        "status": "ok",
        "match_count": len(candidates),
        "sample_size": n,
        "average_lbs_per_sqft": avg_ratio,
        "median_lbs_per_sqft": median_ratio,
        "min_lbs_per_sqft": round(min(sorted_ratios), 3),
        "max_lbs_per_sqft": round(max(sorted_ratios), 3),
        "ratio_details": ratio_details,
        "note": "Truthful descriptive statistics from matching historical candidates."
    }


from backend.modules.admin.steel_estimator.historical_estimation import (
    estimate_foundation_steel,
    estimate_basement_steel,
    estimate_ground_floor_steel,
    estimate_upper_floor_steel,
    estimate_roof_steel,
)

def calculate_foundation_steel(
    db: Session, inputs: Dict[str, Any], similarity_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculates foundation steel using ranking-weighted historical COMPLETE_LEVEL foundation evidence.
    """
    norm_inputs = normalize_project_input(inputs)
    if similarity_result is None:
        similarity_result = find_similar_historical_projects(db, norm_inputs)
    return estimate_foundation_steel(similarity_result, norm_inputs)


def calculate_basement_steel(
    db: Session, inputs: Dict[str, Any], similarity_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculates basement steel using complete basement level evidence.
    If basement_count == 0, returns not_applicable and 0 lbs.
    """
    norm_inputs = normalize_project_input(inputs)
    if similarity_result is None:
        similarity_result = find_similar_historical_projects(db, norm_inputs)
    return estimate_basement_steel(similarity_result, norm_inputs)


def calculate_ground_floor_steel(
    db: Session, inputs: Dict[str, Any], similarity_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculates ground-floor steel using complete GROUND level evidence.
    """
    norm_inputs = normalize_project_input(inputs)
    if similarity_result is None:
        similarity_result = find_similar_historical_projects(db, norm_inputs)
    return estimate_ground_floor_steel(similarity_result, norm_inputs)


def calculate_upper_floor_steel(
    db: Session, inputs: Dict[str, Any], similarity_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculates upper-floor steel using complete upper floor level set evidence.
    If above_ground_floors <= 1, returns not_applicable and 0 lbs.
    """
    norm_inputs = normalize_project_input(inputs)
    if similarity_result is None:
        similarity_result = find_similar_historical_projects(db, norm_inputs)
    return estimate_upper_floor_steel(similarity_result, norm_inputs)


def calculate_roof_steel(
    db: Session, inputs: Dict[str, Any], similarity_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculates roof steel.
    Returns explicit insufficient_component_data because historical dataset contains 0 roof records.
    """
    norm_inputs = normalize_project_input(inputs)
    if similarity_result is None:
        similarity_result = find_similar_historical_projects(db, norm_inputs)
    return estimate_roof_steel(similarity_result, norm_inputs)


from backend.modules.admin.steel_estimator.final_estimation import (
    estimate_whole_project_steel,
    calculate_evidence_confidence as calc_confidence,
    normalize_market_price,
    evaluate_steel_material_cost as eval_material_cost,
)

def aggregate_steel_estimate(
    db: Session,
    inputs: Dict[str, Any],
    components: Dict[str, Dict[str, Any]],
    similarity_result: Optional[Dict[str, Any]] = None,
    fetch_market_price: bool = True
) -> Dict[str, Any]:
    """
    Aggregates whole-project historical steel estimate with supporting component breakdown.
    Primary result comes from whole-project historical weighted ratio (estimate_whole_project_steel),
    NOT component summation, and NOT old 4.5/6.8 fallback.
    """
    norm_inputs = normalize_project_input(inputs)
    if similarity_result is None:
        similarity_result = find_similar_historical_projects(db, norm_inputs)

    # Primary whole-project total estimate
    total_est = estimate_whole_project_steel(similarity_result, norm_inputs)

    # Check component consistency warning (R23)
    warnings = []
    tot_net_lbs = total_est.get("estimated_net_lbs")
    if tot_net_lbs:
        for cname, cdata in components.items():
            if isinstance(cdata, dict):
                c_lbs = cdata.get("estimated_net_lbs") or cdata.get("estimated_rebar_lbs")
                if c_lbs and c_lbs > tot_net_lbs:
                    warnings.append(
                        f"component_consistency_warning: {cname} net lbs ({c_lbs:,.2f}) > total project net lbs ({tot_net_lbs:,.2f})"
                    )

    # Evidence confidence
    used_samples = total_est.get("historical_samples", [])
    confidence = calc_confidence(used_samples)

    # Market price & material cost
    market_price = None
    material_cost = None
    if fetch_market_price:
        loc = norm_inputs.get("location", "US")
        market_price = normalize_market_price(loc)
        material_cost = eval_material_cost(total_est, market_price)

    # Determine overall status
    if total_est.get("status") == "insufficient_historical_data":
        status = "insufficient_historical_data"
    elif market_price and market_price.get("status") != "ok":
        status = "estimate_available_price_unavailable"
    elif total_est.get("status") == "limited_evidence":
        status = "limited_evidence"
    else:
        status = "ok"

    return {
        "status": status,
        "project_inputs": norm_inputs,
        "steel_specification": {
            "material": "Reinforcement Steel / Rebar",
            "grade": "Grade 60",
            "weight_unit": "LBS",
            "display_ton_unit": "US short ton"
        },
        "total_estimate": total_est,
        "component_breakdown": {
            "complete": False,
            **components
        },
        "confidence": confidence,
        "market_price": market_price,
        "material_cost": material_cost,
        "historical_samples": used_samples,
        "warnings": warnings,
        # Legacy compatibility fields:
        "total_sqft_calculated": norm_inputs.get("total_covered_area_sqft"),
        "estimated_rebar_tons": total_est.get("estimated_net_us_tons"),
        "steel_grade": "Grade 60",
    }


def get_grade60_market_price(location: str) -> Dict[str, Any]:
    """
    Retrieves Grade 60 market pricing for location via shared Tavily integration.
    """
    return normalize_market_price(location)


def calculate_steel_material_cost(rebar_tons: float, price_per_ton: float) -> Dict[str, Any]:
    """
    Calculates material cost in backend Python: total_rebar_tons * market_price_per_ton.
    """
    total_est = {"estimated_net_us_tons": rebar_tons, "estimated_with_wastage_us_tons": None}
    price_info = {"normalized_price_usd_per_us_ton": price_per_ton}
    return eval_material_cost(total_est, price_info)


def calculate_estimate_confidence(
    inputs: Dict[str, Any],
    historical_analysis: Dict[str, Any],
    cost_requested: bool = False,
    market_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Deterministically evaluates estimate confidence.
    """
    samples = historical_analysis.get("historical_samples", []) or historical_analysis.get("candidates", [])
    return calc_confidence(samples)

