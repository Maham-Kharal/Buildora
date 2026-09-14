from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class AdminReceiptItemSchema(BaseModel):
    item_name: str
    quantity: float
    unit_price: float
    total_price: float

class AdminReceiptDetailSchema(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_email: str
    image_url: str
    vendor_name: Optional[str]
    total_amount: float
    purchase_date: Optional[date]
    category: Optional[str]
    status: str
    flagged_anomaly: bool
    created_at: datetime
    items: List[AdminReceiptItemSchema] = []

    class Config:
        from_attributes = True

class StatusUpdateSchema(BaseModel):
    status: str # APPROVED or REJECTED
