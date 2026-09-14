from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.deps import get_db, require_role
from backend.db.models import User
from backend.modules.admin.expense_reports.schemas import ExpenseReportSummarySchema
from backend.modules.admin.expense_reports.service import generate_financial_expense_report

router = APIRouter(prefix="/admin/expense-reports", tags=["Admin - Expense Reports"])

@router.get("/summary", response_model=ExpenseReportSummarySchema)
def get_expense_summary(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["ADMIN"]))
):
    """Generate financial expense report metrics and category breakdown ($USD)."""
    return generate_financial_expense_report(db)
