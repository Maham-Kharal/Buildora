from pydantic import BaseModel
from typing import List, Optional

class SteelEstimateRequestSchema(BaseModel):
    project_name: str
    project_type: str # e.g. Commercial, Residential, Bridge, Industrial
    total_sqft: float
    rebar_grade: str = "Grade 60"
    location: str = "Texas, US"

class SimilarProjectSchema(BaseModel):
    name: str
    project_type: str
    sqft: float
    steel_tons_used: float
    cost_usd: float
    location: str
    similarity_score: float

class SteelEstimateResponseSchema(BaseModel):
    project_name: str
    total_sqft: float
    estimated_rebar_tons: float
    live_market_price_per_ton: float
    total_estimated_cost_usd: float
    currency: str = "USD"
    market_source: str
    similar_historical_projects: List[SimilarProjectSchema] = []
