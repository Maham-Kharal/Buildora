from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class AssignedProjectOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class ReceiptItemSchema(BaseModel):
    item_name: str
    quantity: float
    unit_price: float
    total_price: float

class ReceiptResponseSchema(BaseModel):
    id: int
    user_id: int
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    image_url: str
    vendor_name: Optional[str]
    total_amount: float
    purchase_date: Optional[date]
    category: Optional[str]
    status: str
    flagged_anomaly: bool
    created_at: datetime
    items: List[ReceiptItemSchema] = []

    class Config:
        from_attributes = True