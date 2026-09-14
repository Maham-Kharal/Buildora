from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.deps import get_db, require_role
from backend.db.models import User
from backend.modules.admin.steel_estimator.schemas import SteelEstimateRequestSchema, SteelEstimateResponseSchema
from backend.modules.admin.steel_estimator.service import calculate_steel_estimation

router = APIRouter(prefix="/admin/steel-estimator", tags=["Admin - AI Steel Estimator"])

@router.post("/estimate", response_model=SteelEstimateResponseSchema)
def estimate_steel(
    request: SteelEstimateRequestSchema,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["ADMIN"]))
):
    """Estimate Grade 60 Rebar tonnage & US market pricing with 25 historical project similarity search."""
    return calculate_steel_estimation(db, request)