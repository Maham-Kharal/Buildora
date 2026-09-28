import math
from sqlalchemy.orm import Session
from backend.db.models import HistoricalProject
from backend.shared.ai.tavily import get_market_steel_price
from backend.modules.admin.steel_estimator.schemas import (
    SteelEstimateRequestSchema, SteelEstimateResponseSchema, SimilarProjectSchema
)

def calculate_steel_estimation(db: Session, request: SteelEstimateRequestSchema) -> SteelEstimateResponseSchema:
    """
    Service estimation endpoint refactored for Change 5.
    Uses whole-project historical similarity-weighted net ratio.
    Removes hardcoded 4.5 / 6.8 fallback.
    """
    inputs = {
        "total_covered_area_sqft": request.total_sqft,
        "building_type": request.project_type or "Commercial",
        "basement_count": 0,
        "above_ground_floors": 1,
        "structural_system": request.project_type or "Reinforced Concrete Moment Frame",
        "foundation_type": "Spread Footings",
        "floor_system": "Slab on Grade",
        "location": request.location or "Texas, US",
    }

    from backend.modules.admin.steel_estimator.tools import find_similar_historical_projects
    from backend.modules.admin.steel_estimator.final_estimation import (
        estimate_whole_project_steel,
        normalize_market_price,
        evaluate_steel_material_cost,
    )

    similarity_res = find_similar_historical_projects(db, inputs, top_k=5)
    total_est = estimate_whole_project_steel(similarity_res, inputs)

    market_info = normalize_market_price(request.location)
    cost_info = evaluate_steel_material_cost(total_est, market_info)

    est_tons = total_est.get("estimated_net_us_tons") or 0.0
    market_price = market_info.get("normalized_price_usd_per_us_ton") or 0.0
    total_cost = cost_info.get("final_material_cost_usd") or 0.0

    similar_list = []
    candidates = similarity_res.get("candidates", [])[:3]
    for c in candidates:
        ev = c.get("evidence", {}).get("project_total", {})
        net_lbs = ev.get("total_rebar_net_lbs") or c.get("total_rebar_net_lbs")
        similar_list.append(
            SimilarProjectSchema(
                name=c.get("project_title"),
                project_type=c.get("building_type", "Unknown"),
                sqft=c.get("total_covered_area_sqft"),
                steel_tons_used=round(net_lbs / 2000.0, 2) if net_lbs else None,
                cost_usd=None,
                location=c.get("location", "Unknown"),
                similarity_score=round(c.get("similarity_score", 0.0) * 100.0, 1),
            )
        )

    weighted_ratio = total_est.get("weighted_net_ratio", 0.0)
    steps = (
        f"1. Similarity Weighted Whole-Project Historical Ratio: {weighted_ratio:.4f} lbs/sqft\n"
        f"2. Total Covered Area: {request.total_sqft:,.0f} sqft\n"
        f"3. Estimated Net Rebar Weight: {total_est.get('estimated_net_lbs', 0):,.2f} lbs\n"
        f"4. Rebar Tonnage: {est_tons:,.2f} US Short Tons\n"
        f"5. Grade 60 Verified Market Rate: ${market_price:,.2f} USD / US Short Ton\n"
        f"6. Final Material Cost: ${total_cost:,.2f} USD ({cost_info.get('cost_basis', 'net_quantity')})"
    )

    return SteelEstimateResponseSchema(
        project_name=request.project_name,
        total_sqft=request.total_sqft,
        estimated_rebar_tons=est_tons,
        live_market_price_per_ton=market_price,
        total_estimated_cost_usd=total_cost,
        market_source=market_info.get("source", "Tavily Steel Search API"),
        search_query_used=market_info.get("query_used"),
        calculation_steps=steps,
        similar_historical_projects=similar_list,
    )