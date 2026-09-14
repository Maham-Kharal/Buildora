from typing import List
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from backend.core.deps import get_db, get_current_user
from backend.db.models import User
from backend.modules.user.receipt_submission.schemas import ReceiptResponseSchema
from backend.modules.user.receipt_submission.service import process_and_create_receipt, get_user_submitted_receipts

router = APIRouter(prefix="/user/receipts", tags=["Worker - Receipt Submission"])

@router.post("/upload", response_model=ReceiptResponseSchema)
def upload_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a construction receipt image, extract data using Gemini AI Vision OCR, and persist details."""
    return process_and_create_receipt(db, current_user, file)

@router.get("/my-receipts", response_model=List[ReceiptResponseSchema])
def get_my_receipts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch all receipts submitted by the logged-in user."""
    return get_user_submitted_receipts(db, current_user.id)