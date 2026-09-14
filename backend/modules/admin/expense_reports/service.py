from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.db.models import Receipt
from backend.modules.admin.expense_reports.schemas import ExpenseReportSummarySchema, CategoryBreakdownSchema

def generate_financial_expense_report(db: Session) -> ExpenseReportSummarySchema:
    receipts = db.query(Receipt).all()
    
    total_spend = sum(r.total_amount for r in receipts)
    total_receipts = len(receipts)
    flagged_anomalies = sum(1 for r in receipts if r.flagged_anomaly)
    pending_count = sum(1 for r in receipts if r.status == "PENDING")
    approved_count = sum(1 for r in receipts if r.status == "APPROVED")
    rejected_count = sum(1 for r in receipts if r.status == "REJECTED")

    cat_map = {}
    for r in receipts:
        cat = r.category or "Uncategorized"
        if cat not in cat_map:
            cat_map[cat] = {"total": 0.0, "count": 0}
        cat_map[cat]["total"] += r.total_amount
        cat_map[cat]["count"] += 1

    by_category = [
        CategoryBreakdownSchema(
            category=k,
            total_amount=round(v["total"], 2),
            receipt_count=v["count"]
        ) for k, v in cat_map.items()
    ]

    return ExpenseReportSummarySchema(
        total_spend_usd=round(total_spend, 2),
        total_receipts=total_receipts,
        flagged_anomalies_count=flagged_anomalies,
        pending_approval_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        by_category=by_category
    )