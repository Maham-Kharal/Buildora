from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.deps import get_db, require_role
from backend.db.models import User
from backend.modules.admin.receipt_monitoring.schemas import AdminReceiptDetailSchema, StatusUpdateSchema
from backend.modules.admin.receipt_monitoring.service import get_all_monitored_receipts, update_receipt_approval_status

router = APIRouter(prefix="/admin/receipts", tags=["Admin - Receipt Monitoring"])

@router.get("", response_model=List[AdminReceiptDetailSchema])
def get_receipts(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["ADMIN"]))
):
    """Retrieve all submitted receipts across users for admin review & anomaly inspection."""
    return get_all_monitored_receipts(db)

@router.patch("/{receipt_id}/status")
def update_status(
    receipt_id: int,
    payload: StatusUpdateSchema,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["ADMIN"]))
):
    """Approve or Reject a submitted expense receipt."""
    return update_receipt_approval_status(db, admin_user.id, receipt_id, payload.status)