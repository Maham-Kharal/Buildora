import os
from sqlalchemy.orm import Session
from fastapi import UploadFile
from datetime import datetime
from backend.db.models import Receipt, ReceiptItem, AuditLog, User
from backend.shared.storage import save_uploaded_file
from backend.shared.ai.gemini import parse_receipt_with_gemini
from backend.shared.ai.tavily import get_market_steel_price, check_price_anomaly

def process_and_create_receipt(db: Session, user: User, file: UploadFile):
    # Save file to disk
    image_url = save_uploaded_file(file)
    
    # Absolute local path for Gemini vision OCR
    abs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), image_url.lstrip("/"))
    
    # Perform Gemini OCR
    ocr_data = parse_receipt_with_gemini(abs_path)
    
    # Check Tavily price anomaly threshold (15% benchmark)
    benchmark_steel = get_market_steel_price()
    benchmark_unit = benchmark_steel.get("market_price_per_ton", 980.0) / 2000.0 # ~$0.49/lb
    
    is_anomaly = False
    items_objs = []
    
    for item in ocr_data.get("items", []):
        unit_price = item.get("unit_price", 0.0)
        if check_price_anomaly(unit_price, benchmark_unit):
            is_anomaly = True
        
        items_objs.append(ReceiptItem(
            item_name=item.get("name", "Construction Item"),
            quantity=item.get("quantity", 1.0),
            unit_price=unit_price,
            total_price=item.get("total_price", unit_price)
        ))
    
    purchase_date_str = ocr_data.get("purchase_date")
    p_date = None
    if purchase_date_str:
        try:
            p_date = datetime.strptime(purchase_date_str, "%Y-%m-%d").date()
        except Exception:
            p_date = datetime.utcnow().date()

    # Create Receipt DB record
    receipt = Receipt(
        user_id=user.id,
        image_url=image_url,
        vendor_name=ocr_data.get("vendor_name", "Unknown Vendor"),
        total_amount=float(ocr_data.get("total_amount", 0.0)),
        purchase_date=p_date,
        category=ocr_data.get("category", "Materials"),
        status="PENDING",
        flagged_anomaly=is_anomaly,
        items=items_objs
    )
    
    db.add(receipt)
    
    # Audit log entry
    audit = AuditLog(
        user_id=user.id,
        action="RECEIPT_SUBMISSION",
        details=f"Submitted receipt from {receipt.vendor_name} for ${receipt.total_amount:.2f} USD."
    )
    db.add(audit)
    
    db.commit()
    db.refresh(receipt)
    return receipt

def get_user_submitted_receipts(db: Session, user_id: int):
    return db.query(Receipt).filter(Receipt.user_id == user_id).order_by(Receipt.created_at.desc()).all()
