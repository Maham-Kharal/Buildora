import math
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.shared.ai.tavily import get_market_steel_price

logger = logging.getLogger("buildora.final_estimation")

MAX_TOTAL_EVIDENCE_PROJECTS = 5

CONFIDENCE_SIMILARITY_WEIGHT = 0.30
CONFIDENCE_COVERAGE_WEIGHT = 0.25
CONFIDENCE_SAMPLE_WEIGHT = 0.20
CONFIDENCE_CONSISTENCY_WEIGHT = 0.25


# ------------------------------------------------------------------------------
# 1. Whole-Project Total Historical Steel Estimator
# ------------------------------------------------------------------------------
def estimate_whole_project_steel(
    similarity_result: Dict[str, Any],
    user_inputs: Dict[str, Any],
    max_projects: int = MAX_TOTAL_EVIDENCE_PROJECTS
) -> Dict[str, Any]:
    """
    Estimates total project steel quantity using ranking-weighted whole-project historical evidence.
    Does NOT sum component estimates. Applies user_total_covered_area_sqft exactly ONCE.
    """
    user_sqft = user_inputs.get("total_covered_area_sqft")
    if not user_sqft or user_sqft <= 0:
        return {
            "status": "insufficient_historical_data",
            "method": "similarity_weighted_whole_project_historical_ratio",
            "ratio_basis": "total_rebar_lbs_per_total_covered_sqft",
            "user_total_covered_area_sqft": user_sqft,
            "reason": "Invalid user_total_covered_area_sqft.",
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
        }

    candidates = similarity_result.get("candidates", [])
    usable_net_samples = []
    usable_wastage_samples = []
    excluded_samples = []

    for c in candidates:
        if c.get("data_quality") == "REFERENCE":
            continue

        p_key = c["project_key"]
        p_title = c["project_title"]
        r_score = c["ranking_score"]
        s_score = c["similarity_score"]
        c_score = c["coverage_score"]
        h_sqft = c.get("total_covered_area_sqft")

        ev_total = c.get("evidence", {}).get("project_total", {})
        net_lbs = ev_total.get("total_rebar_net_lbs")

        if r_score > 0 and h_sqft and h_sqft > 0 and net_lbs and net_lbs > 0:
            net_ratio = round(net_lbs / float(h_sqft), 6)
            sample_item = {
                "project_key": p_key,
                "project_title": p_title,
                "ranking_score": r_score,
                "similarity_score": s_score,
                "coverage_score": c_score,
                "historical_total_covered_area_sqft": h_sqft,
                "historical_total_rebar_net_lbs": net_lbs,
                "historical_net_ratio": net_ratio,
                "data_quality": c.get("data_quality", "SOURCE_VERIFIED"),
            }
            usable_net_samples.append(sample_item)

            # Check with-wastage quantity
            wastage_lbs = getattr(c, "total_rebar_with_wastage_lbs", None) or ev_total.get("total_rebar_with_wastage_lbs")
            if wastage_lbs and wastage_lbs >= net_lbs:
                wastage_ratio = round(wastage_lbs / float(h_sqft), 6)
                usable_wastage_samples.append({
                    **sample_item,
                    "historical_total_rebar_with_wastage_lbs": wastage_lbs,
                    "historical_wastage_ratio": wastage_ratio,
                })
            elif wastage_lbs and wastage_lbs < net_lbs:
                logger.warning(f"Excluding invalid wastage record in {p_key}: wastage_lbs ({wastage_lbs}) < net_lbs ({net_lbs})")
        else:
            reason = "ranking_score <= 0" if r_score <= 0 else ("Missing/invalid historical area" if not h_sqft else "Missing/invalid total rebar net lbs")
            excluded_samples.append({"project_key": p_key, "project_title": p_title, "reason": reason})

    # Take top max_projects sorted by ranking_score DESC
    usable_net_samples.sort(key=lambda x: (-x["ranking_score"], x["project_key"]))
    used_net = usable_net_samples[:max_projects]

    usable_wastage_samples.sort(key=lambda x: (-x["ranking_score"], x["project_key"]))
    used_wastage = usable_wastage_samples[:max_projects]

    if not used_net:
        return {
            "status": "insufficient_historical_data",
            "method": "similarity_weighted_whole_project_historical_ratio",
            "ratio_basis": "total_rebar_lbs_per_total_covered_sqft",
            "user_total_covered_area_sqft": user_sqft,
            "historical_projects_available": len(candidates),
            "historical_projects_used": 0,
            "estimated_net_lbs": None,
            "estimated_net_us_tons": None,
            "reason": "No valid whole-project historical evidence with ranking_score > 0.",
        }

    # Compute weighted ratios
    sum_net_weights = sum(s["ranking_score"] for s in used_net)
    weighted_net_ratio = round(sum(s["ranking_score"] * s["historical_net_ratio"] for s in used_net) / sum_net_weights, 6)

    est_net_lbs = round(weighted_net_ratio * user_sqft, 2)
    est_net_tons = round(est_net_lbs / 2000.0, 2)

    weighted_wastage_ratio = None
    est_wastage_lbs = None
    est_wastage_tons = None

    if used_wastage:
        sum_wastage_weights = sum(s["ranking_score"] for s in used_wastage)
        if sum_wastage_weights > 0:
            weighted_wastage_ratio = round(sum(s["ranking_score"] * s["historical_wastage_ratio"] for s in used_wastage) / sum_wastage_weights, 6)
            est_wastage_lbs = round(weighted_wastage_ratio * user_sqft, 2)
            est_wastage_tons = round(est_wastage_lbs / 2000.0, 2)

    status = "ok" if len(used_net) >= 2 else "limited_evidence"

    # Descriptive statistics on usable ratios
    net_ratios = [s["historical_net_ratio"] for s in used_net]
    sorted_ratios = sorted(net_ratios)
    n = len(sorted_ratios)
    median_ratio = round(sorted_ratios[n // 2] if n % 2 == 1 else (sorted_ratios[n // 2 - 1] + sorted_ratios[n // 2]) / 2.0, 4)

    return {
        "status": status,
        "method": "similarity_weighted_whole_project_historical_ratio",
        "ratio_basis": "total_rebar_lbs_per_total_covered_sqft",
        "user_total_covered_area_sqft": user_sqft,
        "historical_projects_available": len(candidates),
        "historical_projects_used": len(used_net),
        "weighted_net_ratio": weighted_net_ratio,
        "estimated_net_lbs": est_net_lbs,
        "estimated_net_us_tons": est_net_tons,
        "weighted_with_wastage_ratio": weighted_wastage_ratio,
        "estimated_with_wastage_lbs": est_wastage_lbs,
        "estimated_with_wastage_us_tons": est_wastage_tons,
        "descriptive_statistics": {
            "sample_count": n,
            "min_ratio": round(min(sorted_ratios), 4),
            "max_ratio": round(max(sorted_ratios), 4),
            "median_ratio": median_ratio,
            "arithmetic_mean_ratio": round(sum(sorted_ratios) / float(n), 4),
            "weighted_ratio": weighted_net_ratio,
        },
        "historical_samples": used_net,
        "wastage_samples": used_wastage,
    }


# ------------------------------------------------------------------------------
# 2. Deterministic Evidence Confidence Evaluator
# ------------------------------------------------------------------------------
def calculate_evidence_confidence(used_samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates transparent deterministic evidence confidence across 4 dimensions:
    similarity_strength, coverage_strength, sample_strength, and consistency_strength.
    Applies small-sample caps: 1 sample -> max 0.45, 2 samples -> max 0.65.
    """
    sample_count = len(used_samples)
    if sample_count == 0:
        return {
            "status": "UNAVAILABLE",
            "evidence_confidence_score": 0.0,
            "display_score": 0,
            "label": "UNAVAILABLE",
            "sample_count": 0,
            "interpretation": "No historical samples available for confidence evaluation."
        }

    # A. Similarity Strength
    similarity_strength = round(sum(s.get("similarity_score", 0.0) for s in used_samples) / float(sample_count), 4)

    # B. Coverage Strength
    coverage_strength = round(sum(s.get("coverage_score", 0.0) for s in used_samples) / float(sample_count), 4)

    # C. Sample Strength (out of 5)
    sample_strength = round(min(sample_count / float(MAX_TOTAL_EVIDENCE_PROJECTS), 1.0), 4)

    # D. Consistency Strength (for >= 2 samples)
    cv = None
    if sample_count >= 2:
        sum_weights = sum(s.get("ranking_score", 1.0) for s in used_samples)
        mu = sum(s.get("ranking_score", 1.0) * s["historical_net_ratio"] for s in used_samples) / sum_weights
        variance = sum(s.get("ranking_score", 1.0) * ((s["historical_net_ratio"] - mu) ** 2) for s in used_samples) / sum_weights
        weighted_std = math.sqrt(variance)
        cv = round(weighted_std / mu, 4) if mu > 0 else 0.0
        consistency_strength = round(1.0 / (1.0 + cv), 4)
        consistency_status = "ok"
    else:
        consistency_strength = 0.0
        consistency_status = "unavailable_single_sample"

    # Raw Confidence
    raw_confidence = (
        CONFIDENCE_SIMILARITY_WEIGHT * similarity_strength +
        CONFIDENCE_COVERAGE_WEIGHT * coverage_strength +
        CONFIDENCE_SAMPLE_WEIGHT * sample_strength +
        CONFIDENCE_CONSISTENCY_WEIGHT * consistency_strength
    )
    raw_confidence = round(raw_confidence, 4)

    # Small-sample caps
    if sample_count == 1:
        confidence = min(raw_confidence, 0.45)
    elif sample_count == 2:
        confidence = min(raw_confidence, 0.65)
    else:
        confidence = raw_confidence

    confidence = round(confidence, 4)
    display_score = int(round(confidence * 100))

    # Label assignment
    if confidence >= 0.75 and sample_count >= 3:
        label = "HIGH"
    elif confidence >= 0.55:
        label = "MODERATE"
    else:
        label = "LOW"

    return {
        "status": "ok",
        "evidence_confidence_score": confidence,
        "display_score": display_score,
        "label": label,
        "similarity_strength": similarity_strength,
        "coverage_strength": coverage_strength,
        "sample_strength": sample_strength,
        "consistency_strength": consistency_strength,
        "consistency_status": consistency_status,
        "coefficient_of_variation": cv,
        "sample_count": sample_count,
        "small_sample_cap_applied": confidence < raw_confidence,
        "interpretation": "Deterministic evidence-quality heuristic, not a statistical probability or engineering guarantee."
    }


# ------------------------------------------------------------------------------
# 3. Market Price Normalization & Provenance
# ------------------------------------------------------------------------------
def normalize_market_price(location: str = "Texas, US") -> Dict[str, Any]:
    """
    Fetches real-time market price via Tavily integration and normalizes unit to USD / US short ton.
    Rejects zero, negative, or ambiguous prices.
    """
    raw_data = get_market_steel_price(location)

    raw_price = raw_data.get("market_price_per_ton")
    if not raw_price or raw_price <= 0:
        return {
            "status": "unavailable",
            "reason": "Market price search returned non-positive price.",
            "normalized_price_usd_per_us_ton": None,
        }

    # Tavily default benchmark is USD / US short ton
    raw_unit = "US short ton"
    currency = raw_data.get("currency", "USD")

    return {
        "status": "ok",
        "normalized_price_usd_per_us_ton": round(float(raw_price), 2),
        "raw_price": raw_price,
        "currency": currency,
        "raw_unit": raw_unit,
        "location": location,
        "retrieval_date": raw_data.get("retrieval_date"),
        "source": raw_data.get("source", "Tavily Steel Search API"),
        "query_used": raw_data.get("query_used"),
        "web_sources": raw_data.get("web_sources", []),
    }


# ------------------------------------------------------------------------------
# 4. Steel Material Cost Evaluation
# ------------------------------------------------------------------------------
def evaluate_steel_material_cost(
    total_estimate: Dict[str, Any], market_price_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates steel material cost = US short tons * price_per_us_ton.
    Prefers with-wastage quantity when available.
    """
    price_per_ton = market_price_info.get("normalized_price_usd_per_us_ton")
    if not price_per_ton or price_per_ton <= 0:
        return {
            "status": "unavailable",
            "reason": "Valid market price per US short ton unavailable.",
            "net_material_cost_usd": None,
            "with_wastage_material_cost_usd": None,
            "final_material_cost_usd": None,
            "cost_basis": "none",
        }

    net_tons = total_estimate.get("estimated_net_us_tons")
    wastage_tons = total_estimate.get("estimated_with_wastage_us_tons")

    net_cost = round(net_tons * price_per_ton, 2) if net_tons else None
    wastage_cost = round(wastage_tons * price_per_ton, 2) if wastage_tons else None

    if wastage_cost is not None:
        final_cost = wastage_cost
        basis = "historical_with_wastage_quantity"
        note = "Material cost based on historical with-wastage quantity."
    elif net_cost is not None:
        final_cost = net_cost
        basis = "net_quantity_only"
        note = "Historical wastage quantity unavailable; material cost excludes wastage allowance."
    else:
        return {
            "status": "unavailable",
            "reason": "No estimated steel tonnage available for cost calculation.",
            "final_material_cost_usd": None,
            "cost_basis": "none",
        }

    return {
        "status": "ok",
        "market_price_per_us_ton": price_per_ton,
        "net_material_cost_usd": net_cost,
        "with_wastage_material_cost_usd": wastage_cost,
        "final_material_cost_usd": final_cost,
        "cost_basis": basis,
        "formatted_final_cost": f"${final_cost:,.2f} USD",
        "cost_scope": "STEEL MATERIAL COST ONLY (excludes labor, transport, tax, fabrication)",
        "note": note,
    }
