from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.db.models import Receipt, User, AuditLog
from backend.modules.admin.receipt_monitoring.schemas import AdminReceiptDetailSchema

def get_all_monitored_receipts(db: Session):
    receipts = db.query(Receipt).order_by(Receipt.created_at.desc()).all()
    results = []
    for r in receipts:
        user = db.query(User).filter(User.id == r.user_id).first()
        results.append(AdminReceiptDetailSchema(
            id=r.id,
            user_id=r.user_id,
            user_name=user.full_name if user else "Unknown",
            user_email=user.email if user else "",
            image_url=r.image_url,
            vendor_name=r.vendor_name,
            total_amount=r.total_amount,
            purchase_date=r.purchase_date,
            category=r.category,
            status=r.status,
            flagged_anomaly=r.flagged_anomaly,
            created_at=r.created_at,
            items=[{
                "item_name": item.item_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price
            } for item in r.items]
        ))
    return results

def update_receipt_approval_status(db: Session, admin_id: int, receipt_id: int, new_status: str):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    receipt.status = new_status
    audit = AuditLog(
        user_id=admin_id,
        action="RECEIPT_STATUS_UPDATE",
        details=f"Admin updated receipt #{receipt_id} status to {new_status}."
    )
    db.add(audit)
    db.commit()
    db.refresh(receipt)
    return receipt
