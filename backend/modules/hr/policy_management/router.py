from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from backend.core.deps import get_db, get_current_user, require_role
from backend.db.models import User
from backend.modules.hr.policy_management.schemas import PolicyDocumentOut
from backend.modules.hr.policy_management.service import (
    upload_policy_document,
    list_policy_documents,
    delete_policy_document
)

router = APIRouter(prefix="/hr/policies", tags=["HR - Company Policy Management"])

@router.get("", response_model=List[PolicyDocumentOut])
def get_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all active company policy document metadata."""
    return list_policy_documents(db)

@router.post("/upload", response_model=PolicyDocumentOut)
def upload_policy(
    title: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_role(["HR_MANAGER", "ADMIN"]))
):
    """Upload a complete HR company policy document (PDF, DOCX, TXT)."""
    return upload_policy_document(
        db=db,
        hr_id=hr_user.id,
        title=title,
        category=category,
        file=file
    )

@router.delete("/{policy_id}")
def remove_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_role(["HR_MANAGER", "ADMIN"]))
):
    """Delete a company policy document and its stored file."""
    return delete_policy_document(db, hr_user.id, policy_id)
