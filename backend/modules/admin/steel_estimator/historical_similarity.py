import re
from typing import Dict, Any, List, Optional, Tuple

# ------------------------------------------------------------------------------
# Centralized Configurable Similarity Weights (Total = 100)
# ------------------------------------------------------------------------------
SIMILARITY_WEIGHTS: Dict[str, float] = {
    "total_covered_area_sqft": 20.0,
    "building_type": 10.0,
    "basement_count": 10.0,
    "above_ground_floors": 10.0,
    "structural_system": 15.0,
    "foundation_type": 15.0,
    "floor_system": 15.0,
    "location": 5.0,
}

TOTAL_WEIGHT: float = sum(SIMILARITY_WEIGHTS.values())  # 100.0


# ------------------------------------------------------------------------------
# Normalization & Explicit Alias Maps
# ------------------------------------------------------------------------------
def normalize_string(val: Optional[str]) -> Optional[str]:
    """Trims, lowercases, and collapses whitespace and punctuation in input strings."""
    if val is None:
        return None
    s = str(val).strip().lower()
    s = re.sub(r"[\-_,/\s]+", " ", s)
    s = s.strip()
    return s if s else None


# Explicit Alias Mappings for Categorical Fields
STRUCTURAL_SYSTEM_ALIASES: Dict[str, str] = {
    "rcc frame": "reinforced concrete frame",
    "reinforced concrete frame": "reinforced concrete frame",
    "rc frame": "reinforced concrete frame",
    "reinforced concrete moment frame": "reinforced concrete frame",
    "wood light frame": "wood / light frame",
    "wood / light frame": "wood / light frame",
    "wood frame": "wood / light frame",
    "light frame": "wood / light frame",
    "wood": "wood / light frame",
    "mixed": "mixed",
}

FOUNDATION_TYPE_ALIASES: Dict[str, str] = {
    "mat foundation": "mat foundation",
    "raft foundation": "mat foundation",
    "mat": "mat foundation",
    "spread footing": "spread footing",
    "footing": "spread footing",
    "pad footing": "spread footing",
    "isolated footing": "spread footing",
    "grade beam": "grade beam",
    "pile foundation": "pile foundation",
    "pile": "pile foundation",
    "mixed": "mixed",
}

FLOOR_SYSTEM_ALIASES: Dict[str, str] = {
    "beam slab": "beam & slab",
    "beam & slab": "beam & slab",
    "beam and slab": "beam & slab",
    "flat slab": "flat slab",
    "flat plate": "flat slab",
    "wood joist beam": "wood joist & beam",
    "wood joist & beam": "wood joist & beam",
    "wood joist and beam": "wood joist & beam",
    "wood joist": "wood joist & beam",
}

BUILDING_TYPE_ALIASES: Dict[str, str] = {
    "residential": "residential",
    "commercial": "commercial",
    "mixed use": "mixed use",
    "mixed-use": "mixed use",
    "mixed": "mixed use",
}


def canonicalize_category(val: Optional[str], alias_map: Dict[str, str]) -> Optional[str]:
    norm = normalize_string(val)
    if norm is None:
        return None
    return alias_map.get(norm, norm)


# ------------------------------------------------------------------------------
# Feature Similarity Scoring Functions
# ------------------------------------------------------------------------------
def score_area_similarity(user_area: Optional[float], hist_area: Optional[float]) -> Tuple[str, Optional[float]]:
    """Symmetric continuous ratio: min(u, h) / max(u, h)"""
    if user_area is None or hist_area is None or user_area <= 0 or hist_area <= 0:
        return "UNKNOWN", None
    u, h = float(user_area), float(hist_area)
    score = round(min(u, h) / max(u, h), 4)
    status = "MATCHED" if score == 1.0 else ("PARTIAL_MATCH" if score > 0.0 else "MISMATCHED")
    return status, score


def score_floors_similarity(user_floors: Optional[int], hist_floors: Optional[int]) -> Tuple[str, Optional[float]]:
    """Deterministic numeric closeness: 1 - abs(u - h) / max(u, h, 1)"""
    if user_floors is None or hist_floors is None:
        return "UNKNOWN", None
    u, h = int(user_floors), int(hist_floors)
    if u < 1 or h < 1:
        return "UNKNOWN", None
    diff = abs(u - h)
    denom = max(u, h, 1)
    score = max(0.0, round(1.0 - (diff / float(denom)), 4))
    status = "MATCHED" if score == 1.0 else ("PARTIAL_MATCH" if score > 0.0 else "MISMATCHED")
    return status, score


def score_basement_similarity(user_b: Optional[int], hist_b: Optional[int]) -> Tuple[str, Optional[float]]:
    """Categorical basement count: exact=1.0, diff=1 -> 0.5, diff>=2 -> 0.0"""
    if user_b is None or hist_b is None:
        return "UNKNOWN", None
    u, h = int(user_b), int(hist_b)
    diff = abs(u - h)
    if diff == 0:
        return "MATCHED", 1.0
    elif diff == 1:
        return "PARTIAL_MATCH", 0.5
    else:
        return "MISMATCHED", 0.0


def score_categorical_similarity(
    user_val: Optional[str], hist_val: Optional[str], alias_map: Dict[str, str]
) -> Tuple[str, Optional[float]]:
    """Exact canonical alias match=1.0, mismatch=0.0, missing=UNKNOWN"""
    u_canon = canonicalize_category(user_val, alias_map)
    h_canon = canonicalize_category(hist_val, alias_map)

    if u_canon is None or h_canon is None:
        return "UNKNOWN", None
    if u_canon == h_canon:
        return "MATCHED", 1.0
    return "MISMATCHED", 0.0


def parse_location(loc_str: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Parses (city, state) from location string."""
    if not loc_str:
        return None, None
    s = loc_str.strip()
    state_match = re.search(r"\b([A-Z]{2})\b", s)
    state = state_match.group(1).upper() if state_match else None
    
    # Try parsing city before state or comma
    parts = [p.strip() for p in s.split(",") if p.strip()]
    city = None
    if len(parts) >= 2:
        # e.g., "160 S Union Ave, Los Angeles, CA 90026" -> parts[1] is Los Angeles
        city = parts[-2].lower()
        city = re.sub(r"^(east|west|north|south)\s+", "", city)
    elif len(parts) == 1:
        city = parts[0].lower()

    return city, state


def score_location_similarity(user_loc: Optional[str], hist_loc: Optional[str]) -> Tuple[str, Optional[float]]:
    """Same city+state=1.0, same state=0.5, diff state=0.0, incomplete=UNKNOWN"""
    if not user_loc or not hist_loc:
        return "UNKNOWN", None

    u_city, u_state = parse_location(user_loc)
    h_city, h_state = parse_location(hist_loc)

    if not u_state or not h_state:
        return "UNKNOWN", None

    if u_state != h_state:
        return "MISMATCHED", 0.0

    if u_city and h_city and (u_city == h_city or u_city in h_city or h_city in u_city):
        return "MATCHED", 1.0

    return "PARTIAL_MATCH", 0.5


# ------------------------------------------------------------------------------
# Comprehensive Candidate Similarity Evaluator
# ------------------------------------------------------------------------------
def evaluate_project_similarity(
    user_inputs: Dict[str, Any], historical_proj: Any
) -> Dict[str, Any]:
    """
    Evaluates similarity score, coverage score, and ranking score for a historical project candidate.
    Excludes UNKNOWN features from similarity denominator.
    """
    feature_evaluators = {
        "total_covered_area_sqft": lambda u, h: score_area_similarity(u, h),
        "building_type": lambda u, h: score_categorical_similarity(u, h, BUILDING_TYPE_ALIASES),
        "basement_count": lambda u, h: score_basement_similarity(u, h),
        "above_ground_floors": lambda u, h: score_floors_similarity(u, h),
        "structural_system": lambda u, h: score_categorical_similarity(u, h, STRUCTURAL_SYSTEM_ALIASES),
        "foundation_type": lambda u, h: score_categorical_similarity(u, h, FOUNDATION_TYPE_ALIASES),
        "floor_system": lambda u, h: score_categorical_similarity(u, h, FLOOR_SYSTEM_ALIASES),
        "location": lambda u, h: score_location_similarity(u, h),
    }

    feature_scores: Dict[str, Dict[str, Any]] = {}
    matched_fields: List[str] = []
    partial_match_fields: List[str] = []
    mismatched_fields: List[str] = []
    unknown_fields: List[str] = []

    sum_weighted_scores = 0.0
    available_weight = 0.0
    user_supplied_weight = 0.0

    for feat, weight in SIMILARITY_WEIGHTS.items():
        u_val = user_inputs.get(feat)
        # Extract attribute from ORM object or dict
        if isinstance(historical_proj, dict):
            h_val = historical_proj.get(feat)
        else:
            h_val = getattr(historical_proj, feat, None)

        if u_val is not None:
            user_supplied_weight += weight

        eval_fn = feature_evaluators[feat]
        status, score = eval_fn(u_val, h_val)

        feature_scores[feat] = {
            "status": status,
            "score": score,
            "user_value": u_val,
            "historical_value": h_val,
            "weight": weight,
        }

        if status == "UNKNOWN":
            unknown_fields.append(feat)
        else:
            available_weight += weight
            sum_weighted_scores += weight * (score if score is not None else 0.0)
            if status == "MATCHED":
                matched_fields.append(feat)
            elif status == "PARTIAL_MATCH":
                partial_match_fields.append(feat)
            elif status == "MISMATCHED":
                mismatched_fields.append(feat)

    # Calculate 3 distinct metrics
    if available_weight > 0:
        similarity_score = round(sum_weighted_scores / available_weight, 4)
    else:
        similarity_score = 0.0

    target_denom = user_supplied_weight if user_supplied_weight > 0 else TOTAL_WEIGHT
    coverage_score = round(available_weight / target_denom, 4)

    ranking_score = round(similarity_score * coverage_score, 4)

    # Extract historical keys safely
    p_key = getattr(historical_proj, "project_key", None) or (historical_proj.get("project_key") if isinstance(historical_proj, dict) else None)
    p_title = getattr(historical_proj, "project_title", None) or (historical_proj.get("project_title") if isinstance(historical_proj, dict) else None)

    return {
        "project_key": p_key,
        "project_title": p_title,
        "similarity_score": similarity_score,
        "coverage_score": coverage_score,
        "ranking_score": ranking_score,
        "feature_scores": feature_scores,
        "matched_fields": matched_fields,
        "partial_match_fields": partial_match_fields,
        "mismatched_fields": mismatched_fields,
        "unknown_fields": unknown_fields,
    }


# ------------------------------------------------------------------------------
# Evidence Profile Evaluator
# ------------------------------------------------------------------------------
FOUNDATION_COMPONENT_TYPES = {
    "PILE", "PIER", "FOOTING", "MAT_FOOTING", "PAD_FOOTING",
    "ISOLATED_FOOTING", "GRADE_BEAM", "GRADE_BEAM_REBAR", "FOOTING_REBAR"
}

def evaluate_evidence_profile(historical_proj: Any) -> Dict[str, Any]:
    """
    Identifies what structural steel evidence actually exists for a historical project
    without summing quantities or fabricating missing levels.
    """
    total_rebar = getattr(historical_proj, "total_rebar_net_lbs", None)
    total_sqft = getattr(historical_proj, "total_covered_area_sqft", None)

    # 1. Project Total Evidence
    project_total_avail = total_rebar is not None and total_rebar > 0
    ratio_avail = project_total_avail and (total_sqft is not None and total_sqft > 0)

    # Levels & Components lists
    levels = getattr(historical_proj, "levels", []) or []
    components = getattr(historical_proj, "steel_components", []) or []

    # 2. Foundation Evidence
    found_levels = [l for l in levels if (getattr(l, "level_type", "") or "").upper() == "FOUNDATION" and (getattr(l, "rebar_net_lbs", None) or 0) > 0]
    found_comps = []
    for c in components:
        ctype = (getattr(c, "component_type", "") or "").upper()
        net_lbs = getattr(c, "rebar_net_lbs", None) or 0
        if net_lbs > 0 and (ctype in FOUNDATION_COMPONENT_TYPES or "FOOTING" in ctype or "GRADE_BEAM" in ctype or "PILE" in ctype):
            found_comps.append(c)

    found_avail = len(found_levels) > 0 or len(found_comps) > 0

    # 3. Basement Evidence (Must explicitly belong to BASEMENT level)
    base_levels = [l for l in levels if (getattr(l, "level_type", "") or "").upper() == "BASEMENT" and (getattr(l, "rebar_net_lbs", None) or 0) > 0]
    base_comps = []
    for c in components:
        net_lbs = getattr(c, "rebar_net_lbs", None) or 0
        lvl = getattr(c, "level", None)
        if net_lbs > 0 and lvl and (getattr(lvl, "level_type", "") or "").upper() == "BASEMENT":
            base_comps.append(c)

    base_avail = len(base_levels) > 0 or len(base_comps) > 0

    # 4. Ground Evidence (Must explicitly belong to GROUND level)
    ground_levels = [l for l in levels if (getattr(l, "level_type", "") or "").upper() == "GROUND" and (getattr(l, "rebar_net_lbs", None) or 0) > 0]
    ground_comps = []
    for c in components:
        net_lbs = getattr(c, "rebar_net_lbs", None) or 0
        lvl = getattr(c, "level", None)
        if net_lbs > 0 and lvl and (getattr(lvl, "level_type", "") or "").upper() == "GROUND":
            ground_comps.append(c)

    ground_avail = len(ground_levels) > 0 or len(ground_comps) > 0

    # 5. Upper Floor Evidence
    upper_levels = [l for l in levels if (getattr(l, "level_type", "") or "").upper() == "UPPER_FLOOR" and (getattr(l, "rebar_net_lbs", None) or 0) > 0]
    upper_comps = []
    for c in components:
        net_lbs = getattr(c, "rebar_net_lbs", None) or 0
        lvl = getattr(c, "level", None)
        if net_lbs > 0 and lvl and (getattr(lvl, "level_type", "") or "").upper() == "UPPER_FLOOR":
            upper_comps.append(c)

    upper_avail = len(upper_levels) > 0 or len(upper_comps) > 0

    # 6. Roof Evidence (Currently 0 projects in historical dataset have roof-isolated steel)
    roof_levels = [l for l in levels if (getattr(l, "level_type", "") or "").upper() == "ROOF" and (getattr(l, "rebar_net_lbs", None) or 0) > 0]
    roof_comps = []
    for c in components:
        net_lbs = getattr(c, "rebar_net_lbs", None) or 0
        lvl = getattr(c, "level", None)
        if net_lbs > 0 and lvl and (getattr(lvl, "level_type", "") or "").upper() == "ROOF":
            roof_comps.append(c)

    roof_avail = len(roof_levels) > 0 or len(roof_comps) > 0

    def format_levels_meta(lvl_list):
        return [
            {
                "level_key": getattr(l, "level_key", None),
                "level_type": getattr(l, "level_type", None),
                "rebar_net_lbs": getattr(l, "rebar_net_lbs", None),
                "quantity_scope": getattr(l, "quantity_scope", "COMPLETE_LEVEL"),
            }
            for l in lvl_list
        ]

    def format_comps_meta(comp_list):
        return [
            {
                "component_key": getattr(c, "component_key", None),
                "component_type": getattr(c, "component_type", None),
                "rebar_net_lbs": getattr(c, "rebar_net_lbs", None),
                "level_key": getattr(getattr(c, "level", None), "level_key", None),
            }
            for c in comp_list
        ]

    return {
        "project_total": {
            "available": project_total_avail,
            "ratio_available": ratio_avail,
            "total_rebar_net_lbs": total_rebar,
            "total_covered_area_sqft": total_sqft,
            "overall_rebar_ratio_lbs_per_sqft": getattr(historical_proj, "overall_rebar_ratio_lbs_per_sqft", None)
        },
        "foundation": {
            "available": found_avail,
            "level_rows_count": len(found_levels),
            "component_rows_count": len(found_comps),
            "levels": format_levels_meta(found_levels),
            "components": format_comps_meta(found_comps),
        },
        "basement": {
            "available": base_avail,
            "level_rows_count": len(base_levels),
            "component_rows_count": len(base_comps),
            "levels": format_levels_meta(base_levels),
            "components": format_comps_meta(base_comps),
        },
        "ground": {
            "available": ground_avail,
            "level_rows_count": len(ground_levels),
            "component_rows_count": len(ground_comps),
            "levels": format_levels_meta(ground_levels),
            "components": format_comps_meta(ground_comps),
        },
        "upper_floor": {
            "available": upper_avail,
            "level_rows_count": len(upper_levels),
            "component_rows_count": len(upper_comps),
            "levels": format_levels_meta(upper_levels),
            "components": format_comps_meta(upper_comps),
        },
        "roof": {
            "available": roof_avail,
            "level_rows_count": len(roof_levels),
            "component_rows_count": len(roof_comps),
            "levels": format_levels_meta(roof_levels),
            "components": format_comps_meta(roof_comps),
        },
    }


# ------------------------------------------------------------------------------
# Deterministic Ranking & Evidence Pool Builder
# ------------------------------------------------------------------------------
def rank_and_build_evidence_pools(
    user_inputs: Dict[str, Any],
    historical_projects: List[Any],
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Ranks source-backed historical projects deterministically and constructs separate evidence pools.
    Excludes REFERENCE dataset projects by default.
    """
    top_k = max(1, min(10, top_k))
    evaluated_candidates = []

    for hp in historical_projects:
        # Exclude REFERENCE projects (e.g. P022) by default
        dq = getattr(hp, "data_quality", "") or (hp.get("data_quality") if isinstance(hp, dict) else "")
        if dq == "REFERENCE":
            continue

        sim_res = evaluate_project_similarity(user_inputs, hp)
        ev_profile = evaluate_evidence_profile(hp)

        candidate = {
            **sim_res,
            "location": getattr(hp, "location", None),
            "building_type": getattr(hp, "building_type", None),
            "total_covered_area_sqft": getattr(hp, "total_covered_area_sqft", None),
            "data_quality": dq,
            "evidence": ev_profile,
        }
        evaluated_candidates.append(candidate)

    # Sort deterministically: ranking_score DESC, similarity_score DESC, coverage_score DESC, project_key ASC
    evaluated_candidates.sort(
        key=lambda x: (
            -x["ranking_score"],
            -x["similarity_score"],
            -x["coverage_score"],
            x["project_key"] or ""
        )
    )

    ranked_top = evaluated_candidates[:top_k]

    # Build Evidence Pools from ranked candidates
    evidence_pools = {
        "project_total": [],
        "foundation": [],
        "basement": [],
        "ground": [],
        "upper_floor": [],
        "roof": [],
    }

    for cand in ranked_top:
        ev = cand["evidence"]
        cand_summary = {
            "project_key": cand["project_key"],
            "project_title": cand["project_title"],
            "ranking_score": cand["ranking_score"],
            "similarity_score": cand["similarity_score"],
            "coverage_score": cand["coverage_score"],
        }

        if ev["project_total"]["available"]:
            evidence_pools["project_total"].append({**cand_summary, "evidence_details": ev["project_total"]})
        if ev["foundation"]["available"]:
            evidence_pools["foundation"].append({**cand_summary, "evidence_details": ev["foundation"]})
        if ev["basement"]["available"]:
            evidence_pools["basement"].append({**cand_summary, "evidence_details": ev["basement"]})
        if ev["ground"]["available"]:
            evidence_pools["ground"].append({**cand_summary, "evidence_details": ev["ground"]})
        if ev["upper_floor"]["available"]:
            evidence_pools["upper_floor"].append({**cand_summary, "evidence_details": ev["upper_floor"]})
        if ev["roof"]["available"]:
            evidence_pools["roof"].append({**cand_summary, "evidence_details": ev["roof"]})

    return {
        "status": "ok",
        "query_inputs": user_inputs,
        "dataset_summary": {
            "source_backed_projects_considered": len(evaluated_candidates),
            "reference_projects_excluded": len([p for p in historical_projects if (getattr(p, "data_quality", "") or "") == "REFERENCE"]),
            "top_k_returned": len(ranked_top),
        },
        "candidates": ranked_top,
        "evidence_pools": evidence_pools,
    }
