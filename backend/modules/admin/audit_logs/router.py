from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.deps import get_db, require_role
from backend.db.models import User
from backend.modules.admin.audit_logs.schemas import AuditLogSchema
from backend.modules.admin.audit_logs.service import get_system_audit_logs

router = APIRouter(prefix="/admin/audit-logs", tags=["Admin - Audit Trails"])

@router.get("", response_model=List[AuditLogSchema])
def list_audit_logs(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["ADMIN"]))
):
    """Retrieve immutable system audit logs for administrative monitoring."""
    return get_system_audit_logs(db)