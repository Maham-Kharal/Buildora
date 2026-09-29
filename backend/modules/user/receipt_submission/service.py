import os
import logging
from sqlalchemy.orm import Session, joinedload
from fastapi import UploadFile, HTTPException
from datetime import datetime
from backend.db.models import Receipt, ReceiptItem, AuditLog, User, ActiveProject, ProjectMember
from backend.shared.storage import save_uploaded_file
from backend.shared.ai.gemini import (
    parse_receipt_with_gemini,
    OCRQuotaExceededError,
    OCRUnreadableError,
)
from backend.shared.ai.tavily import get_market_steel_price, check_price_anomaly

logger = logging.getLogger("buildora.receipts")



def get_assigned_active_projects(db: Session, user_id: int):
    """Return active projects assigned to current user via ProjectMember."""
    results = (
        db.query(ActiveProject.id, ActiveProject.name, ActiveProject.location)
        .join(ProjectMember, ProjectMember.project_id == ActiveProject.id)
        .filter(
            ProjectMember.user_id == user_id,
            ActiveProject.status == "ACTIVE"
        )
        .distinct()
        .order_by(ActiveProject.name.asc(), ActiveProject.id.asc())
        .all()
    )

    from collections import Counter
    name_counts = Counter(r.name for r in results)

    out = []
    for r in results:
        if name_counts[r.name] > 1:
            display_name = f"{r.name} (Project #{r.id})"
        else:
            display_name = r.name
        out.append({"id": r.id, "name": display_name})

    return out


def format_receipt_response(receipt: Receipt):
    """Format a Receipt ORM entity into a dict matching ReceiptResponseSchema."""
    project_name = receipt.project.name if receipt.project else None
    return {
        "id": receipt.id,
        "user_id": receipt.user_id,
        "project_id": receipt.project_id,
        "project_name": project_name,
        "image_url": receipt.image_url,
        "vendor_name": receipt.vendor_name,
        "total_amount": receipt.total_amount,
        "purchase_date": receipt.purchase_date,
        "category": receipt.category,
        "status": receipt.status,
        "flagged_anomaly": receipt.flagged_anomaly,
        "created_at": receipt.created_at,
        "items": [
            {
                "item_name": item.item_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
            }
            for item in receipt.items
        ],
    }


def process_and_create_receipt(db: Session, user: User, file: UploadFile, project_id: int):
    # 1. Authorize project membership BEFORE file saving or OCR execution
    project = (
        db.query(ActiveProject)
        .join(ProjectMember, ProjectMember.project_id == ActiveProject.id)
        .filter(
            ProjectMember.user_id == user.id,
            ProjectMember.project_id == project_id,
            ActiveProject.status == "ACTIVE"
        )
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You are not assigned to this active project."
        )

    # 2. Save file to disk
    image_url = save_uploaded_file(file)

    # Absolute local path for Gemini vision OCR
    abs_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        image_url.lstrip("/")
    )

    # 3. Perform Gemini OCR
    try:
        ocr_data = parse_receipt_with_gemini(abs_path)
        if not ocr_data or (not ocr_data.get("vendor_name") and float(ocr_data.get("total_amount", 0.0)) == 0.0 and not ocr_data.get("items")):
            raise OCRUnreadableError("Insufficient details extracted from receipt image.")
    except OCRQuotaExceededError as e:
        logger.error(f"Receipt OCR quota exceeded: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Receipt scanning is temporarily unavailable because the AI OCR service has reached its usage limit. Please try again later."
        )
    except OCRUnreadableError as e:
        logger.warning(f"Receipt OCR unreadable image: {e}")
        raise HTTPException(
            status_code=400,
            detail="We couldn't clearly read this receipt. Please upload a clearer, well-lit image."
        )
    except Exception as e:
        err_str = str(e).lower()
        logger.error(f"Receipt OCR service exception: {e}", exc_info=True)
        if any(q in err_str for q in ["429", "resource_exhausted", "quota", "rate limit", "limit reached", "usage limit"]):
            raise HTTPException(
                status_code=503,
                detail="Receipt scanning is temporarily unavailable because the AI OCR service has reached its usage limit. Please try again later."
            )
        elif any(u in err_str for u in ["unreadable", "clearer", "cannot read"]):
            raise HTTPException(
                status_code=400,
                detail="We couldn't clearly read this receipt. Please upload a clearer, well-lit image."
            )
        else:
            raise HTTPException(
                status_code=503,
                detail="Receipt scanning service encountered an error. Please try again later."
            )

    # 4. Check Tavily price anomaly threshold (15% benchmark)
    benchmark_steel = get_market_steel_price()
    benchmark_unit = benchmark_steel.get("market_price_per_ton", 980.0) / 2000.0  # ~$0.49/lb

    is_anomaly = False
    items_objs = []

    for item in ocr_data.get("items", []):
        unit_price = item.get("unit_price", 0.0)
        if check_price_anomaly(unit_price, benchmark_unit):
            is_anomaly = True

        items_objs.append(
            ReceiptItem(
                item_name=item.get("name", "Construction Item"),
                quantity=item.get("quantity", 1.0),
                unit_price=unit_price,
                total_price=item.get("total_price", unit_price),
            )
        )

    purchase_date_str = ocr_data.get("purchase_date")
    p_date = None
    if purchase_date_str:
        try:
            p_date = datetime.strptime(purchase_date_str, "%Y-%m-%d").date()
        except Exception:
            p_date = datetime.utcnow().date()

    # 5. Create Receipt DB record
    receipt = Receipt(
        user_id=user.id,
        project_id=project.id,
        image_url=image_url,
        vendor_name=ocr_data.get("vendor_name", "Unknown Vendor"),
        total_amount=float(ocr_data.get("total_amount", 0.0)),
        purchase_date=p_date,
        category=ocr_data.get("category", "Materials"),
        status="PENDING",
        flagged_anomaly=is_anomaly,
        items=items_objs,
    )

    db.add(receipt)

    # 6. Audit log entry
    audit = AuditLog(
        user_id=user.id,
        action="RECEIPT_SUBMISSION",
        details=f"Submitted receipt from {receipt.vendor_name} for ${receipt.total_amount:.2f} USD for project '{project.name}' (ID: {project.id}).",
        metadata_info={"project_id": project.id, "project_name": project.name}
    )
    db.add(audit)

    db.commit()
    db.refresh(receipt)
    return format_receipt_response(receipt)


def get_user_submitted_receipts(db: Session, user_id: int):
    receipts = (
        db.query(Receipt)
        .options(joinedload(Receipt.project))
        .filter(Receipt.user_id == user_id)
        .order_by(Receipt.created_at.desc())
        .all()
    )
    return [format_receipt_response(r) for r in receipts]


