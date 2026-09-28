from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class SteelEstimateRequestSchema(BaseModel):
    project_name: str
    project_type: str # e.g. Commercial, Residential, Bridge, Industrial
    total_sqft: float
    rebar_grade: str = "Grade 60"
    location: str = "Texas, US"

class SimilarProjectSchema(BaseModel):
    name: str  # Compatibility alias for project_title
    project_type: str  # Building type / structural classification
    sqft: Optional[float] = None  # Compatibility alias for total_covered_area_sqft
    steel_tons_used: Optional[float] = None  # Derived metric: total_rebar_net_lbs / 2000.0
    cost_usd: Optional[float] = None  # Optional: historical cost is not available in dataset
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
    search_query_used: Optional[str] = None
    calculation_steps: Optional[str] = None
    similar_historical_projects: List[SimilarProjectSchema] = []


class FeatureScoreDetail(BaseModel):
    status: str  # MATCHED, PARTIAL_MATCH, MISMATCHED, UNKNOWN
    score: Optional[float] = None
    user_value: Any = None
    historical_value: Any = None
    weight: float


class CandidateMatchSchema(BaseModel):
    project_key: str
    project_title: str
    similarity_score: float
    coverage_score: float
    ranking_score: float
    feature_scores: Dict[str, FeatureScoreDetail]
    matched_fields: List[str] = []
    partial_match_fields: List[str] = []
    mismatched_fields: List[str] = []
    unknown_fields: List[str] = []
    evidence: Dict[str, Any] = {}
    location: Optional[str] = None
    building_type: Optional[str] = None
    total_covered_area_sqft: Optional[float] = None
    data_quality: str = "SOURCE_VERIFIED"


class EvidencePoolItemSchema(BaseModel):
    project_key: str
    project_title: str
    ranking_score: float
    similarity_score: float
    coverage_score: float
    evidence_details: Dict[str, Any] = {}


class EvidencePoolsSchema(BaseModel):
    project_total: List[EvidencePoolItemSchema] = []
    foundation: List[EvidencePoolItemSchema] = []
    basement: List[EvidencePoolItemSchema] = []
    ground: List[EvidencePoolItemSchema] = []
    upper_floor: List[EvidencePoolItemSchema] = []
class HistoricalSimilarityResponseSchema(BaseModel):
    status: str = "ok"
    query_inputs: Dict[str, Any] = {}
    dataset_summary: Dict[str, Any] = {}
    candidates: List[CandidateMatchSchema] = []
    evidence_pools: EvidencePoolsSchema = EvidencePoolsSchema()


class HistoricalSampleDetail(BaseModel):
    project_key: str
    project_title: str
    ranking_score: float
    similarity_score: float
    coverage_score: float
    historical_total_covered_area_sqft: float
    historical_component_net_lbs: float
    historical_component_net_ratio: float
    historical_component_with_wastage_lbs: Optional[float] = None
    historical_component_wastage_ratio: Optional[float] = None
    quantity_source: str
    quantity_scope: str = "COMPLETE_LEVEL"
    usable_for_point_estimate: bool = True


class SupportingEvidenceDetail(BaseModel):
    project_key: str
    project_title: str
    ranking_score: float
    quantity_scope: Optional[str] = None
    usable_for_point_estimate: bool = False
    exclusion_reason: str
    level_rows_count: Optional[int] = None
    component_rows_count: Optional[int] = None


class ComponentEstimateSchema(BaseModel):
    status: str  # ok, limited_evidence, insufficient_component_data, not_applicable
    component: str  # foundation, basement, ground_floor, upper_floors, roof
    method: str = "similarity_weighted_historical_ratio"
    ratio_basis: str = "component_lbs_per_total_covered_sqft"
    user_total_covered_area_sqft: Optional[float] = None
    evidence: Dict[str, Any] = {}
    weighted_net_ratio_lbs_per_total_covered_sqft: Optional[float] = None
    estimated_net_lbs: Optional[float] = None
    estimated_net_us_tons: Optional[float] = None
    weighted_wastage_ratio_lbs_per_total_covered_sqft: Optional[float] = None
    estimated_with_wastage_lbs: Optional[float] = None
    estimated_with_wastage_us_tons: Optional[float] = None
    historical_samples: List[HistoricalSampleDetail] = []
    supporting_evidence: List[SupportingEvidenceDetail] = []
    reason: Optional[str] = None
    note: Optional[str] = None


class TotalSteelEstimateSchema(BaseModel):
    status: str  # ok, limited_evidence, insufficient_historical_data
    method: str = "similarity_weighted_whole_project_historical_ratio"
    ratio_basis: str = "total_rebar_lbs_per_total_covered_sqft"
    user_total_covered_area_sqft: Optional[float] = None
    historical_projects_available: int = 0
    historical_projects_used: int = 0
    weighted_net_ratio: Optional[float] = None
    estimated_net_lbs: Optional[float] = None
    estimated_net_us_tons: Optional[float] = None
    weighted_with_wastage_ratio: Optional[float] = None
    estimated_with_wastage_lbs: Optional[float] = None
    estimated_with_wastage_us_tons: Optional[float] = None
    descriptive_statistics: Dict[str, Any] = {}
    historical_samples: List[Dict[str, Any]] = []


class EvidenceConfidenceSchema(BaseModel):
    status: str = "ok"
    evidence_confidence_score: float = 0.0
    display_score: int = 0
    label: str = "LOW"  # HIGH, MODERATE, LOW, UNAVAILABLE
    similarity_strength: float = 0.0
    coverage_strength: float = 0.0
    sample_strength: float = 0.0
    consistency_strength: float = 0.0
    consistency_status: str = "ok"
    coefficient_of_variation: Optional[float] = None
    sample_count: int = 0
    small_sample_cap_applied: bool = False
    interpretation: str = "Deterministic evidence-quality heuristic, not a statistical probability or engineering guarantee."


class MarketPriceDetailSchema(BaseModel):
    status: str = "ok"
    normalized_price_usd_per_us_ton: Optional[float] = None
    raw_price: Optional[float] = None
    currency: str = "USD"
    raw_unit: str = "US short ton"
    location: str = "Texas, US"
    retrieval_date: Optional[str] = None
    source: str = "Tavily Steel Search API"
    query_used: Optional[str] = None
    web_sources: List[Dict[str, Any]] = []


class MaterialCostDetailSchema(BaseModel):
    status: str = "ok"
    market_price_per_us_ton: Optional[float] = None
    net_material_cost_usd: Optional[float] = None
    with_wastage_material_cost_usd: Optional[float] = None
    final_material_cost_usd: Optional[float] = None
    cost_basis: str = "none"
    formatted_final_cost: Optional[str] = None
    cost_scope: str = "STEEL MATERIAL COST ONLY (excludes labor, transport, tax, fabrication)"
    note: Optional[str] = None


class FinalSteelEstimateResponseSchema(BaseModel):
    status: str = "ok"  # ok, estimate_available_price_unavailable, limited_evidence, insufficient_historical_data
    project_inputs: Dict[str, Any] = {}
    steel_specification: Dict[str, str] = {
        "material": "Reinforcement Steel / Rebar",
        "grade": "Grade 60",
        "weight_unit": "LBS",
        "display_ton_unit": "US short ton"
    }
    total_estimate: TotalSteelEstimateSchema
    component_breakdown: Dict[str, Any] = {}
    component_breakdown_complete: bool = False
    confidence: EvidenceConfidenceSchema
    market_price: MarketPriceDetailSchema
    material_cost: MaterialCostDetailSchema
    historical_samples: List[Dict[str, Any]] = []
    warnings: List[str] = []
