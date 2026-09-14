from pydantic import BaseModel
from typing import Dict, List

class CategoryBreakdownSchema(BaseModel):
    category: str
    total_amount: float
    receipt_count: int

class ExpenseReportSummarySchema(BaseModel):
    total_spend_usd: float
    total_receipts: int
    flagged_anomalies_count: int
    pending_approval_count: int
    approved_count: int
    rejected_count: int
    by_category: List[CategoryBreakdownSchema]
