import math
from sqlalchemy.orm import Session
from backend.db.models import HistoricalProject
from backend.shared.ai.tavily import get_market_steel_price
from backend.modules.admin.steel_estimator.schemas import (
    SteelEstimateRequestSchema, SteelEstimateResponseSchema, SimilarProjectSchema
)

def calculate_steel_estimation(db: Session, request: SteelEstimateRequestSchema) -> SteelEstimateResponseSchema:
    # US Construction estimation standard for Grade 60 steel:
    # ~4.5 lbs of rebar per sqft for commercial / residential foundations and slabs
    # 1 US ton = 2000 lbs
    lbs_per_sqft = 4.5
    if "bridge" in request.project_type.lower() or "industrial" in request.project_type.lower():
        lbs_per_sqft = 6.8 # Higher density for structural heavy civil
        
    estimated_lbs = request.total_sqft * lbs_per_sqft
    estimated_tons = round(estimated_lbs / 2000.0, 2)
    
    # Get Tavily real-time market price per ton
    market_data = get_market_steel_price(request.location)
    market_price = market_data.get("market_price_per_ton", 980.0)
    total_cost = round(estimated_tons * market_price, 2)

    # Historical similarity search (using absolute difference in sqft)
    all_projects = db.query(HistoricalProject).all()
    scored_projects = []
    
    for hp in all_projects:
        sqft_diff = abs(hp.sqft - request.total_sqft)
        # Similarity percentage metric: 100% - (diff / max(hp.sqft, target_sqft))
        max_sq = max(hp.sqft, request.total_sqft)
        score = max(0.0, round((1.0 - (sqft_diff / max_sq)) * 100.0, 1))
        
        scored_projects.append((score, hp))
        
    # Sort top 3 similar past projects
    scored_projects.sort(key=lambda x: x[0], reverse=True)
    top_3 = scored_projects[:3]

    similar_list = [
        SimilarProjectSchema(
            name=hp.name,
            project_type=hp.project_type,
            sqft=hp.sqft,
            steel_tons_used=hp.steel_tons_used,
            cost_usd=hp.cost_usd,
            location=hp.location,
            similarity_score=score
        ) for score, hp in top_3
    ]

    return SteelEstimateResponseSchema(
        project_name=request.project_name,
        total_sqft=request.total_sqft,
        estimated_rebar_tons=estimated_tons,
        live_market_price_per_ton=market_price,
        total_estimated_cost_usd=total_cost,
        market_source=market_data.get("source", "US Benchmark Market Index"),
        similar_historical_projects=similar_list
    )