import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.modules.admin.steel_estimator.historical_similarity import (
    rank_and_build_evidence_pools,
    FOUNDATION_COMPONENT_TYPES,
)

logger = logging.getLogger("buildora.historical_estimation")

MAX_COMPONENT_EVIDENCE_PROJECTS = 5


# ------------------------------------------------------------------------------
# Core Helper: Weighted Ratio Calculation
# ------------------------------------------------------------------------------
def compute_weighted_ratio(
    usable_samples: List[Dict[str, Any]], ratio_key: str
) -> Tuple[Optional[float], float]:
    """
    Computes:
    weighted_ratio = SUM(ranking_score_i * ratio_i) / SUM(ranking_score_i)
    Only considers samples where ratio_key is present and ranking_score > 0.
    Returns (weighted_ratio, sum_weights).
    """
    valid_samples = [s for s in usable_samples if s.get(ratio_key) is not None and s.get("ranking_score", 0) > 0]
    if not valid_samples:
        return None, 0.0

    sum_weighted_vals = sum(s["ranking_score"] * s[ratio_key] for s in valid_samples)
    sum_weights = sum(s["ranking_score"] for s in valid_samples)

    if sum_weights <= 0:
        return None, 0.0

    return round(sum_weighted_vals / sum_weights, 6), sum_weights


# ------------------------------------------------------------------------------
# Category 1: FOUNDATION STEEL ESTIMATION
# ------------------------------------------------------------------------------
def estimate_foundation_steel(
    similarity_result: Dict[str, Any], user_inputs: Dict[str, Any], max_projects: int = MAX_COMPONENT_EVIDENCE_PROJECTS
) -> Dict[str, Any]:
    """
    Estimates foundation steel using COMPLETE_LEVEL foundation historical evidence.
    """
    user_sqft = user_inputs.get("total_covered_area_sqft")
    if not user_sqft or user_sqft <= 0:
        return {
            "component": "foundation",
            "status": "insufficient_component_data",
            "reason": "Invalid user_total_covered_area_sqft.",
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
        }

    candidates = similarity_result.get("candidates", [])
    usable_samples = []
    supporting_samples = []

    for c in candidates:
        if c.get("data_quality") == "REFERENCE":
            continue

        p_key = c["project_key"]
        p_title = c["project_title"]
        r_score = c["ranking_score"]
        s_score = c["similarity_score"]
        c_score = c["coverage_score"]
        h_sqft = c.get("total_covered_area_sqft")

        ev_found = c.get("evidence", {}).get("foundation", {})
        levels = ev_found.get("levels", [])
        components = ev_found.get("components", [])

        # Check completeness
        complete_levels = [l for l in levels if l.get("quantity_scope") == "COMPLETE_LEVEL" and (l.get("rebar_net_lbs") or 0) > 0]

        if len(complete_levels) == 1 and h_sqft and h_sqft > 0:
            lvl = complete_levels[0]
            net_lbs = lvl["rebar_net_lbs"]
            net_ratio = round(net_lbs / float(h_sqft), 6)

            wastage_lbs = lvl.get("rebar_with_wastage_lbs")
            wastage_ratio = None
            if wastage_lbs is not None and wastage_lbs >= net_lbs:
                wastage_ratio = round(wastage_lbs / float(h_sqft), 6)
            elif wastage_lbs is not None and wastage_lbs < net_lbs:
                logger.warning(f"Invalid wastage record in {p_key}: wastage_lbs ({wastage_lbs}) < net_lbs ({net_lbs})")

            usable_samples.append({
                "project_key": p_key,
                "project_title": p_title,
                "ranking_score": r_score,
                "similarity_score": s_score,
                "coverage_score": c_score,
                "historical_total_covered_area_sqft": h_sqft,
                "historical_component_net_lbs": net_lbs,
                "historical_component_net_ratio": net_ratio,
                "historical_component_with_wastage_lbs": wastage_lbs,
                "historical_component_wastage_ratio": wastage_ratio,
                "quantity_source": "FOUNDATION_COMPLETE_LEVEL",
                "quantity_scope": "COMPLETE_LEVEL",
                "usable_for_point_estimate": True,
            })
        else:
            # Supporting evidence only
            reason = "Missing COMPLETE_LEVEL foundation row" if not complete_levels else ("Multiple foundation levels" if len(complete_levels) > 1 else "Missing total covered area")
            supporting_samples.append({
                "project_key": p_key,
                "project_title": p_title,
                "ranking_score": r_score,
                "quantity_scope": levels[0].get("quantity_scope") if levels else "COMPONENT_ONLY",
                "usable_for_point_estimate": False,
                "exclusion_reason": reason,
                "level_rows_count": len(levels),
                "component_rows_count": len(components),
            })

    # Sort usable samples by ranking_score DESC
    usable_samples.sort(key=lambda x: (-x["ranking_score"], x["project_key"]))
    used_top = usable_samples[:max_projects]

    weighted_net_ratio, sum_net_weights = compute_weighted_ratio(used_top, "historical_component_net_ratio")
    weighted_wastage_ratio, sum_wastage_weights = compute_weighted_ratio(used_top, "historical_component_wastage_ratio")

    if weighted_net_ratio is None or sum_net_weights <= 0:
        return {
            "status": "insufficient_component_data",
            "component": "foundation",
            "method": "similarity_weighted_historical_ratio",
            "ratio_basis": "component_lbs_per_total_covered_sqft",
            "user_total_covered_area_sqft": user_sqft,
            "evidence": {
                "available_projects_in_candidates": len(candidates),
                "usable_for_point_estimate_count": len(usable_samples),
                "projects_used_count": 0,
                "supporting_only_count": len(supporting_samples),
            },
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
            "supporting_evidence": supporting_samples,
            "reason": "No complete foundation evidence with ranking_score > 0.",
        }

    est_net_lbs = round(weighted_net_ratio * user_sqft, 2)
    est_net_tons = round(est_net_lbs / 2000.0, 2)

    est_wastage_lbs = round(weighted_wastage_ratio * user_sqft, 2) if weighted_wastage_ratio else None
    est_wastage_tons = round(est_wastage_lbs / 2000.0, 2) if est_wastage_lbs else None

    status = "ok" if len(used_top) >= 2 else "limited_evidence"

    return {
        "status": status,
        "component": "foundation",
        "method": "similarity_weighted_historical_ratio",
        "ratio_basis": "component_lbs_per_total_covered_sqft",
        "user_total_covered_area_sqft": user_sqft,
        "evidence": {
            "available_projects_in_candidates": len(candidates),
            "usable_for_point_estimate_count": len(usable_samples),
            "projects_used_count": len(used_top),
            "supporting_only_count": len(supporting_samples),
        },
        "weighted_net_ratio_lbs_per_total_covered_sqft": weighted_net_ratio,
        "estimated_net_lbs": est_net_lbs,
        "estimated_net_us_tons": est_net_tons,
        "weighted_wastage_ratio_lbs_per_total_covered_sqft": weighted_wastage_ratio,
        "estimated_with_wastage_lbs": est_wastage_lbs,
        "estimated_with_wastage_us_tons": est_wastage_tons,
        "historical_samples": used_top,
        "supporting_evidence": supporting_samples,
    }


# ------------------------------------------------------------------------------
# Category 2: BASEMENT STEEL ESTIMATION
# ------------------------------------------------------------------------------
def estimate_basement_steel(
    similarity_result: Dict[str, Any], user_inputs: Dict[str, Any], max_projects: int = MAX_COMPONENT_EVIDENCE_PROJECTS
) -> Dict[str, Any]:
    """
    Estimates basement steel using complete basement levels.
    If user basement_count == 0, returns status='not_applicable' and 0 lbs.
    """
    user_b_count = user_inputs.get("basement_count", 0) or 0
    user_sqft = user_inputs.get("total_covered_area_sqft")

    if user_b_count == 0:
        return {
            "status": "not_applicable",
            "component": "basement",
            "method": "user_input_zero_basements",
            "user_basement_count": 0,
            "user_total_covered_area_sqft": user_sqft,
            "estimated_net_lbs": 0.0,
            "estimated_net_us_tons": 0.0,
            "estimated_with_wastage_lbs": 0.0,
            "estimated_with_wastage_us_tons": 0.0,
            "note": "User requested 0 basements. Basement steel is not applicable."
        }

    if not user_sqft or user_sqft <= 0:
        return {
            "component": "basement",
            "status": "insufficient_component_data",
            "reason": "Invalid user_total_covered_area_sqft.",
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
        }

    candidates = similarity_result.get("candidates", [])
    usable_samples = []
    supporting_samples = []

    for c in candidates:
        if c.get("data_quality") == "REFERENCE":
            continue

        p_key = c["project_key"]
        p_title = c["project_title"]
        r_score = c["ranking_score"]
        s_score = c["similarity_score"]
        c_score = c["coverage_score"]
        h_sqft = c.get("total_covered_area_sqft")

        # Get basement count from candidate feature details or model
        h_b_count = c.get("feature_scores", {}).get("basement_count", {}).get("historical_value")

        ev_base = c.get("evidence", {}).get("basement", {})
        levels = ev_base.get("levels", [])

        complete_levels = [l for l in levels if l.get("quantity_scope") == "COMPLETE_LEVEL" and (l.get("rebar_net_lbs") or 0) > 0]
        unique_level_keys = set(l.get("level_key") for l in complete_levels)

        # Completeness rule: h_b_count > 0 and len(unique_level_keys) == h_b_count
        if h_b_count and h_b_count > 0 and len(unique_level_keys) == h_b_count and h_sqft and h_sqft > 0:
            net_lbs = sum(l["rebar_net_lbs"] for l in complete_levels)
            net_ratio = round(net_lbs / float(h_sqft), 6)

            wastage_lbs_list = [l.get("rebar_with_wastage_lbs") for l in complete_levels if l.get("rebar_with_wastage_lbs") is not None]
            wastage_lbs = sum(wastage_lbs_list) if len(wastage_lbs_list) == len(complete_levels) else None
            wastage_ratio = None
            if wastage_lbs is not None and wastage_lbs >= net_lbs:
                wastage_ratio = round(wastage_lbs / float(h_sqft), 6)

            usable_samples.append({
                "project_key": p_key,
                "project_title": p_title,
                "ranking_score": r_score,
                "similarity_score": s_score,
                "coverage_score": c_score,
                "historical_total_covered_area_sqft": h_sqft,
                "historical_component_net_lbs": net_lbs,
                "historical_component_net_ratio": net_ratio,
                "historical_component_with_wastage_lbs": wastage_lbs,
                "historical_component_wastage_ratio": wastage_ratio,
                "quantity_source": "BASEMENT_COMPLETE_LEVELS",
                "quantity_scope": "COMPLETE_LEVEL",
                "usable_for_point_estimate": True,
            })
        else:
            reason = f"Incomplete basement levels (found {len(unique_level_keys)} of {h_b_count} expected)" if h_b_count else "Missing historical basement count"
            supporting_samples.append({
                "project_key": p_key,
                "project_title": p_title,
                "ranking_score": r_score,
                "usable_for_point_estimate": False,
                "exclusion_reason": reason,
                "level_rows_count": len(levels),
            })

    usable_samples.sort(key=lambda x: (-x["ranking_score"], x["project_key"]))
    used_top = usable_samples[:max_projects]

    weighted_net_ratio, sum_net_weights = compute_weighted_ratio(used_top, "historical_component_net_ratio")
    weighted_wastage_ratio, sum_wastage_weights = compute_weighted_ratio(used_top, "historical_component_wastage_ratio")

    if weighted_net_ratio is None or sum_net_weights <= 0:
        return {
            "status": "insufficient_component_data",
            "component": "basement",
            "method": "similarity_weighted_historical_ratio",
            "ratio_basis": "component_lbs_per_total_covered_sqft",
            "user_total_covered_area_sqft": user_sqft,
            "evidence": {
                "available_projects_in_candidates": len(candidates),
                "usable_for_point_estimate_count": len(usable_samples),
                "projects_used_count": 0,
                "supporting_only_count": len(supporting_samples),
            },
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
            "supporting_evidence": supporting_samples,
            "reason": "No complete basement level evidence with ranking_score > 0.",
        }

    est_net_lbs = round(weighted_net_ratio * user_sqft, 2)
    est_net_tons = round(est_net_lbs / 2000.0, 2)

    est_wastage_lbs = round(weighted_wastage_ratio * user_sqft, 2) if weighted_wastage_ratio else None
    est_wastage_tons = round(est_wastage_lbs / 2000.0, 2) if est_wastage_lbs else None

    status = "ok" if len(used_top) >= 2 else "limited_evidence"

    return {
        "status": status,
        "component": "basement",
        "method": "similarity_weighted_historical_ratio",
        "ratio_basis": "component_lbs_per_total_covered_sqft",
        "user_total_covered_area_sqft": user_sqft,
        "evidence": {
            "available_projects_in_candidates": len(candidates),
            "usable_for_point_estimate_count": len(usable_samples),
            "projects_used_count": len(used_top),
            "supporting_only_count": len(supporting_samples),
        },
        "weighted_net_ratio_lbs_per_total_covered_sqft": weighted_net_ratio,
        "estimated_net_lbs": est_net_lbs,
        "estimated_net_us_tons": est_net_tons,
        "weighted_wastage_ratio_lbs_per_total_covered_sqft": weighted_wastage_ratio,
        "estimated_with_wastage_lbs": est_wastage_lbs,
        "estimated_with_wastage_us_tons": est_wastage_tons,
        "historical_samples": used_top,
        "supporting_evidence": supporting_samples,
    }


# ------------------------------------------------------------------------------
# Category 3: GROUND FLOOR STEEL ESTIMATION
# ------------------------------------------------------------------------------
def estimate_ground_floor_steel(
    similarity_result: Dict[str, Any], user_inputs: Dict[str, Any], max_projects: int = MAX_COMPONENT_EVIDENCE_PROJECTS
) -> Dict[str, Any]:
    """
    Estimates ground floor steel using COMPLETE_LEVEL GROUND historical evidence.
    Unlinked SOG components remain supporting-only.
    """
    user_sqft = user_inputs.get("total_covered_area_sqft")
    if not user_sqft or user_sqft <= 0:
        return {
            "component": "ground_floor",
            "status": "insufficient_component_data",
            "reason": "Invalid user_total_covered_area_sqft.",
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
        }

    candidates = similarity_result.get("candidates", [])
    usable_samples = []
    supporting_samples = []

    for c in candidates:
        if c.get("data_quality") == "REFERENCE":
            continue

        p_key = c["project_key"]
        p_title = c["project_title"]
        r_score = c["ranking_score"]
        s_score = c["similarity_score"]
        c_score = c["coverage_score"]
        h_sqft = c.get("total_covered_area_sqft")

        ev_ground = c.get("evidence", {}).get("ground", {})
        levels = ev_ground.get("levels", [])

        complete_levels = [l for l in levels if l.get("quantity_scope") == "COMPLETE_LEVEL" and (l.get("rebar_net_lbs") or 0) > 0]

        if len(complete_levels) == 1 and h_sqft and h_sqft > 0:
            lvl = complete_levels[0]
            net_lbs = lvl["rebar_net_lbs"]
            net_ratio = round(net_lbs / float(h_sqft), 6)

            wastage_lbs = lvl.get("rebar_with_wastage_lbs")
            wastage_ratio = None
            if wastage_lbs is not None and wastage_lbs >= net_lbs:
                wastage_ratio = round(wastage_lbs / float(h_sqft), 6)

            usable_samples.append({
                "project_key": p_key,
                "project_title": p_title,
                "ranking_score": r_score,
                "similarity_score": s_score,
                "coverage_score": c_score,
                "historical_total_covered_area_sqft": h_sqft,
                "historical_component_net_lbs": net_lbs,
                "historical_component_net_ratio": net_ratio,
                "historical_component_with_wastage_lbs": wastage_lbs,
                "historical_component_wastage_ratio": wastage_ratio,
                "quantity_source": "GROUND_COMPLETE_LEVEL",
                "quantity_scope": "COMPLETE_LEVEL",
                "usable_for_point_estimate": True,
            })
        else:
            reason = "Missing COMPLETE_LEVEL GROUND row" if not complete_levels else "Multiple ground levels"
            supporting_samples.append({
                "project_key": p_key,
                "project_title": p_title,
                "ranking_score": r_score,
                "quantity_scope": levels[0].get("quantity_scope") if levels else "COMPONENT_ONLY",
                "usable_for_point_estimate": False,
                "exclusion_reason": reason,
                "level_rows_count": len(levels),
            })

    usable_samples.sort(key=lambda x: (-x["ranking_score"], x["project_key"]))
    used_top = usable_samples[:max_projects]

    weighted_net_ratio, sum_net_weights = compute_weighted_ratio(used_top, "historical_component_net_ratio")
    weighted_wastage_ratio, sum_wastage_weights = compute_weighted_ratio(used_top, "historical_component_wastage_ratio")

    if weighted_net_ratio is None or sum_net_weights <= 0:
        return {
            "status": "insufficient_component_data",
            "component": "ground_floor",
            "method": "similarity_weighted_historical_ratio",
            "ratio_basis": "component_lbs_per_total_covered_sqft",
            "user_total_covered_area_sqft": user_sqft,
            "evidence": {
                "available_projects_in_candidates": len(candidates),
                "usable_for_point_estimate_count": len(usable_samples),
                "projects_used_count": 0,
                "supporting_only_count": len(supporting_samples),
            },
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
            "supporting_evidence": supporting_samples,
            "reason": "No complete ground level evidence with ranking_score > 0.",
        }

    est_net_lbs = round(weighted_net_ratio * user_sqft, 2)
    est_net_tons = round(est_net_lbs / 2000.0, 2)

    est_wastage_lbs = round(weighted_wastage_ratio * user_sqft, 2) if weighted_wastage_ratio else None
    est_wastage_tons = round(est_wastage_lbs / 2000.0, 2) if est_wastage_lbs else None

    status = "ok" if len(used_top) >= 2 else "limited_evidence"

    return {
        "status": status,
        "component": "ground_floor",
        "method": "similarity_weighted_historical_ratio",
        "ratio_basis": "component_lbs_per_total_covered_sqft",
        "user_total_covered_area_sqft": user_sqft,
        "evidence": {
            "available_projects_in_candidates": len(candidates),
            "usable_for_point_estimate_count": len(usable_samples),
            "projects_used_count": len(used_top),
            "supporting_only_count": len(supporting_samples),
        },
        "weighted_net_ratio_lbs_per_total_covered_sqft": weighted_net_ratio,
        "estimated_net_lbs": est_net_lbs,
        "estimated_net_us_tons": est_net_tons,
        "weighted_wastage_ratio_lbs_per_total_covered_sqft": weighted_wastage_ratio,
        "estimated_with_wastage_lbs": est_wastage_lbs,
        "estimated_with_wastage_us_tons": est_wastage_tons,
        "historical_samples": used_top,
        "supporting_evidence": supporting_samples,
    }


# ------------------------------------------------------------------------------
# Category 4: UPPER-FLOOR STEEL ESTIMATION
# ------------------------------------------------------------------------------
def estimate_upper_floor_steel(
    similarity_result: Dict[str, Any], user_inputs: Dict[str, Any], max_projects: int = MAX_COMPONENT_EVIDENCE_PROJECTS
) -> Dict[str, Any]:
    """
    Estimates upper-floor steel using complete upper floor levels.
    If user above_ground_floors <= 1, returns status='not_applicable' and 0 lbs.
    """
    ag_floors = user_inputs.get("above_ground_floors", 1) or 1
    user_sqft = user_inputs.get("total_covered_area_sqft")

    if ag_floors <= 1:
        return {
            "status": "not_applicable",
            "component": "upper_floors",
            "method": "user_input_single_story",
            "user_above_ground_floors": ag_floors,
            "user_total_covered_area_sqft": user_sqft,
            "estimated_net_lbs": 0.0,
            "estimated_net_us_tons": 0.0,
            "estimated_with_wastage_lbs": 0.0,
            "estimated_with_wastage_us_tons": 0.0,
            "note": "Building is single-story (1 floor above ground). Upper-floor steel is not applicable."
        }

    if not user_sqft or user_sqft <= 0:
        return {
            "component": "upper_floors",
            "status": "insufficient_component_data",
            "reason": "Invalid user_total_covered_area_sqft.",
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
        }

    candidates = similarity_result.get("candidates", [])
    usable_samples = []
    supporting_samples = []

    for c in candidates:
        if c.get("data_quality") == "REFERENCE":
            continue

        p_key = c["project_key"]
        p_title = c["project_title"]
        r_score = c["ranking_score"]
        s_score = c["similarity_score"]
        c_score = c["coverage_score"]
        h_sqft = c.get("total_covered_area_sqft")

        h_ag = c.get("feature_scores", {}).get("above_ground_floors", {}).get("historical_value")
        exp_upper = max((h_ag - 1), 0) if h_ag else 0

        ev_upper = c.get("evidence", {}).get("upper_floor", {})
        levels = ev_upper.get("levels", [])

        complete_levels = [l for l in levels if l.get("quantity_scope") == "COMPLETE_LEVEL" and (l.get("rebar_net_lbs") or 0) > 0]
        unique_level_keys = set(l.get("level_key") for l in complete_levels)

        # Completeness rule: h_ag > 1 and len(unique_level_keys) == exp_upper
        if h_ag and h_ag > 1 and len(unique_level_keys) == exp_upper and h_sqft and h_sqft > 0:
            net_lbs = sum(l["rebar_net_lbs"] for l in complete_levels)
            net_ratio = round(net_lbs / float(h_sqft), 6)

            wastage_lbs_list = [l.get("rebar_with_wastage_lbs") for l in complete_levels if l.get("rebar_with_wastage_lbs") is not None]
            wastage_lbs = sum(wastage_lbs_list) if len(wastage_lbs_list) == len(complete_levels) else None
            wastage_ratio = None
            if wastage_lbs is not None and wastage_lbs >= net_lbs:
                wastage_ratio = round(wastage_lbs / float(h_sqft), 6)

            usable_samples.append({
                "project_key": p_key,
                "project_title": p_title,
                "ranking_score": r_score,
                "similarity_score": s_score,
                "coverage_score": c_score,
                "historical_total_covered_area_sqft": h_sqft,
                "historical_component_net_lbs": net_lbs,
                "historical_component_net_ratio": net_ratio,
                "historical_component_with_wastage_lbs": wastage_lbs,
                "historical_component_wastage_ratio": wastage_ratio,
                "quantity_source": "UPPER_FLOOR_COMPLETE_LEVEL_SET",
                "quantity_scope": "COMPLETE_LEVEL",
                "usable_for_point_estimate": True,
            })
        else:
            reason = f"Incomplete upper-floor levels (found {len(unique_level_keys)} of {exp_upper} expected)" if h_ag and h_ag > 1 else "Missing or single-story historical floors"
            supporting_samples.append({
                "project_key": p_key,
                "project_title": p_title,
                "ranking_score": r_score,
                "usable_for_point_estimate": False,
                "exclusion_reason": reason,
                "level_rows_count": len(levels),
            })

    usable_samples.sort(key=lambda x: (-x["ranking_score"], x["project_key"]))
    used_top = usable_samples[:max_projects]

    weighted_net_ratio, sum_net_weights = compute_weighted_ratio(used_top, "historical_component_net_ratio")
    weighted_wastage_ratio, sum_wastage_weights = compute_weighted_ratio(used_top, "historical_component_wastage_ratio")

    if weighted_net_ratio is None or sum_net_weights <= 0:
        return {
            "status": "insufficient_component_data",
            "component": "upper_floors",
            "method": "similarity_weighted_historical_ratio",
            "ratio_basis": "component_lbs_per_total_covered_sqft",
            "user_total_covered_area_sqft": user_sqft,
            "evidence": {
                "available_projects_in_candidates": len(candidates),
                "usable_for_point_estimate_count": len(usable_samples),
                "projects_used_count": 0,
                "supporting_only_count": len(supporting_samples),
            },
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
            "supporting_evidence": supporting_samples,
            "reason": "No 100% complete upper floor level evidence with ranking_score > 0.",
        }

    est_net_lbs = round(weighted_net_ratio * user_sqft, 2)
    est_net_tons = round(est_net_lbs / 2000.0, 2)

    est_wastage_lbs = round(weighted_wastage_ratio * user_sqft, 2) if weighted_wastage_ratio else None
    est_wastage_tons = round(est_wastage_lbs / 2000.0, 2) if est_wastage_lbs else None

    status = "ok" if len(used_top) >= 2 else "limited_evidence"

    return {
        "status": status,
        "component": "upper_floors",
        "method": "similarity_weighted_historical_ratio",
        "ratio_basis": "component_lbs_per_total_covered_sqft",
        "user_total_covered_area_sqft": user_sqft,
        "evidence": {
            "available_projects_in_candidates": len(candidates),
            "usable_for_point_estimate_count": len(usable_samples),
            "projects_used_count": len(used_top),
            "supporting_only_count": len(supporting_samples),
        },
        "weighted_net_ratio_lbs_per_total_covered_sqft": weighted_net_ratio,
        "estimated_net_lbs": est_net_lbs,
        "estimated_net_us_tons": est_net_tons,
        "weighted_wastage_ratio_lbs_per_total_covered_sqft": weighted_wastage_ratio,
        "estimated_with_wastage_lbs": est_wastage_lbs,
        "estimated_with_wastage_us_tons": est_wastage_tons,
        "historical_samples": used_top,
        "supporting_evidence": supporting_samples,
    }


# ------------------------------------------------------------------------------
# Category 5: ROOF STEEL ESTIMATION
# ------------------------------------------------------------------------------
def estimate_roof_steel(
    similarity_result: Dict[str, Any], user_inputs: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Roof steel estimation.
    Current historical dataset contains 0 isolated roof steel records.
    Returns explicit insufficient_component_data status without fabricating quantities.
    """
    user_sqft = user_inputs.get("total_covered_area_sqft")
    return {
        "status": "insufficient_component_data",
        "component": "roof",
        "method": "historical_evidence_audit",
        "user_total_covered_area_sqft": user_sqft,
        "evidence": {
            "available_projects_in_candidates": 0,
            "usable_for_point_estimate_count": 0,
            "projects_used_count": 0,
            "supporting_only_count": 0,
        },
        "estimated_net_lbs": None,
        "estimated_net_us_tons": None,
        "estimated_with_wastage_lbs": None,
        "estimated_with_wastage_us_tons": None,
        "reason": "No isolated roof reinforcement evidence exists in the approved historical dataset."
    }
