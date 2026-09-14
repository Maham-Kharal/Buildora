from sqlalchemy.orm import Session
from backend.db.models import AuditLog, User
from backend.modules.admin.audit_logs.schemas import AuditLogSchema

def get_system_audit_logs(db: Session):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    results = []
    for log in logs:
        user = db.query(User).filter(User.id == log.user_id).first() if log.user_id else None
        results.append(AuditLogSchema(
            id=log.id,
            user_id=log.user_id,
            user_name=user.full_name if user else "System",
            action=log.action,
            details=log.details,
            created_at=log.created_at
        ))
    return results