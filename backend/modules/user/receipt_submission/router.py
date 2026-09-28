from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from backend.core.deps import get_db, get_current_user
from backend.db.models import User
from backend.modules.user.receipt_submission.schemas import ReceiptResponseSchema, AssignedProjectOut
from backend.modules.user.receipt_submission.service import (
    process_and_create_receipt,
    get_user_submitted_receipts,
    get_assigned_active_projects,
)

router = APIRouter(prefix="/user/receipts", tags=["Worker - Receipt Submission"])


@router.get("/assigned-projects", response_model=List[AssignedProjectOut])
def list_assigned_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return only active projects assigned to the current logged-in worker."""
    return get_assigned_active_projects(db, current_user.id)


@router.post("/upload", response_model=ReceiptResponseSchema)
def upload_receipt(
    file: UploadFile = File(...),
    project_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a construction receipt image with required project_id, validate project membership, extract data using Gemini AI Vision OCR, and persist details."""
    return process_and_create_receipt(db, current_user, file, project_id)


@router.get("/my-receipts", response_model=List[ReceiptResponseSchema])
def get_my_receipts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch all receipts submitted by the logged-in user."""
    return get_user_submitted_receipts(db, current_user.id)