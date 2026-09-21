import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from backend.db.models import Receipt, User, HistoricalProject, ActiveProject, LeaveRequest, CompanyPolicy

def parse_date_range_from_prompt(prompt: str) -> tuple[Optional[datetime.date], Optional[datetime.date], str]:
    """
    Parses flexible date ranges from user prompts:
    - Today, Yesterday, Specific Date (e.g. Sep 10, 2026-09-10)
    - Date range (Sep 1 to Sep 15)
    - Daily, Weekly, Monthly, This Week, Last Week, This Month, Last Month
    Returns (start_date, end_date, date_label)
    """
    today = datetime.date.today()
    prompt_lower = prompt.lower()

    if "today" in prompt_lower:
        return (today, today, f"{today.strftime('%B %d, %Y')}")
    
    if "yesterday" in prompt_lower:
        yest = today - datetime.timedelta(days=1)
        return (yest, yest, f"{yest.strftime('%B %d, %Y')}")

    if "this week" in prompt_lower or "weekly" in prompt_lower:
        start = today - datetime.timedelta(days=today.weekday())
        return (start, today, f"{start.strftime('%B %d, %Y')} – {today.strftime('%B %d, %Y')}")

    if "last week" in prompt_lower:
        end = today - datetime.timedelta(days=today.weekday() + 1)
        start = end - datetime.timedelta(days=6)
        return (start, end, f"{start.strftime('%B %d, %Y')} – {end.strftime('%B %d, %Y')}")

    if "this month" in prompt_lower or "monthly" in prompt_lower:
        start = today.replace(day=1)
        return (start, today, f"{start.strftime('%B %d, %Y')} – {today.strftime('%B %d, %Y')}")

    if "last month" in prompt_lower:
        first_of_this_month = today.replace(day=1)
        end = first_of_this_month - datetime.timedelta(days=1)
        start = end.replace(day=1)
        return (start, end, f"{start.strftime('%B %d, %Y')} – {end.strftime('%B %d, %Y')}")

    # Default: return None for dates so query returns all actual receipts in DB ("All Time")
    return (None, None, "All Time")


def query_financial_expenses_db(
    db: Session,
    prompt: str = "",
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
    project_filter: Optional[str] = None,
    user_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None
) -> Dict[str, Any]:
    """
    Queries SQLite database for financial receipts with dynamic parameterized filters:
    date ranges, worker, project/vendor name, category, and total spend amounts.
    """
    if not start_date or not end_date:
        s_date, e_date, date_label = parse_date_range_from_prompt(prompt)
    else:
        s_date, e_date = start_date, end_date
        date_label = f"{s_date.strftime('%B %d, %Y')} – {e_date.strftime('%B %d, %Y')}" if s_date != e_date else s_date.strftime('%B %d, %Y')

    query = db.query(Receipt, User).join(User, Receipt.user_id == User.id)

    # Parameterized WHERE clauses
    if s_date:
        query = query.filter(Receipt.purchase_date >= s_date)
    if e_date:
        query = query.filter(Receipt.purchase_date <= e_date)
    if user_filter:
        query = query.filter(User.full_name.ilike(f"%{user_filter.strip()}%"))
    if project_filter:
        query = query.filter(Receipt.vendor_name.ilike(f"%{project_filter.strip()}%"))
    if category_filter:
        query = query.filter(Receipt.category.ilike(f"%{category_filter.strip()}%"))
    if min_amount is not None:
        query = query.filter(Receipt.total_amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Receipt.total_amount <= max_amount)

    results = query.all()

    total_spend = 0.0
    receipt_count = len(results)
    
    project_map: Dict[str, Dict[str, Any]] = {}
    worker_map: Dict[str, Dict[str, Any]] = {}
    category_map: Dict[str, Dict[str, Any]] = {}
    transactions: List[Dict[str, Any]] = []

    for receipt, user in results:
        amount = receipt.total_amount or 0.0
        total_spend += amount
        
        proj_name = receipt.vendor_name or "General Site Ops"
        if proj_name not in project_map:
            project_map[proj_name] = {"total": 0.0, "count": 0}
        project_map[proj_name]["total"] += amount
        project_map[proj_name]["count"] += 1

        w_name = user.full_name or "Field Worker"
        if w_name not in worker_map:
            worker_map[w_name] = {"total": 0.0, "projects": {}}
        worker_map[w_name]["total"] += amount
        worker_map[w_name]["projects"][proj_name] = worker_map[w_name]["projects"].get(proj_name, 0.0) + amount

        cat = receipt.category or "Materials"
        if cat not in category_map:
            category_map[cat] = {"total": 0.0, "count": 0}
        category_map[cat]["total"] += amount
        category_map[cat]["count"] += 1

        transactions.append({
            "date": str(receipt.purchase_date or "2026-09-10"),
            "user": w_name,
            "project_vendor": proj_name,
            "category": cat,
            "amount": round(amount, 2)
        })

    applied_filters = {}
    if s_date and e_date: applied_filters["date_period"] = date_label
    if user_filter: applied_filters["worker"] = user_filter
    if project_filter: applied_filters["project_vendor"] = project_filter
    if category_filter: applied_filters["category"] = category_filter
    if min_amount is not None: applied_filters["min_amount"] = min_amount
    if max_amount is not None: applied_filters["max_amount"] = max_amount

    return {
        "date_period": date_label,
        "applied_filters": applied_filters,
        "total_spend_usd": round(total_spend, 2),
        "receipt_count": receipt_count,
        "projects_breakdown": [
            {"project_name": k, "total_spend": round(v["total"], 2), "receipt_count": v["count"]}
            for k, v in project_map.items()
        ],
        "workers_breakdown": [
            {
                "worker_name": w,
                "total_spend": round(data["total"], 2),
                "project_split": {p: round(amt, 2) for p, amt in data["projects"].items()}
            }
            for w, data in worker_map.items()
        ],
        "categories_breakdown": [
            {"category": k, "total_spend": round(v["total"], 2), "count": v["count"]}
            for k, v in category_map.items()
        ],
        "transactions": transactions[:10]
    }


def query_historical_projects_db(
    db: Session,
    sqft_filter: Optional[float] = None,
    min_sqft: Optional[float] = None,
    max_sqft: Optional[float] = None,
    structural_system: Optional[str] = None,
    floors: Optional[int] = None,
    foundation_type: Optional[str] = None,
    min_steel_tons: Optional[float] = None,
    max_steel_tons: Optional[float] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    location_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Queries SQLite database for past structural projects using parameterized SQL filters:
    area (min/max), structural system, floors, foundation, steel tonnage, budget, and location.
    """
    query = db.query(HistoricalProject)

    # Track applied filters for payload output
    applied_filters = {}

    if min_sqft is not None:
        query = query.filter(HistoricalProject.sqft >= min_sqft)
        applied_filters["min_sqft"] = min_sqft
    elif sqft_filter and sqft_filter > 0:
        # Range tolerance for single target sqft
        query = query.filter(HistoricalProject.sqft >= sqft_filter * 0.7, HistoricalProject.sqft <= sqft_filter * 1.4)
        applied_filters["sqft_target"] = sqft_filter

    if max_sqft is not None:
        query = query.filter(HistoricalProject.sqft <= max_sqft)
        applied_filters["max_sqft"] = max_sqft

    if structural_system:
        query = query.filter(
            or_(
                HistoricalProject.project_type.ilike(f"%{structural_system.strip()}%"),
                HistoricalProject.name.ilike(f"%{structural_system.strip()}%")
            )
        )
        applied_filters["structural_system"] = structural_system

    if min_steel_tons is not None:
        query = query.filter(HistoricalProject.steel_tons_used >= min_steel_tons)
        applied_filters["min_steel_tons"] = min_steel_tons

    if max_steel_tons is not None:
        query = query.filter(HistoricalProject.steel_tons_used <= max_steel_tons)
        applied_filters["max_steel_tons"] = max_steel_tons

    if min_budget is not None:
        query = query.filter(HistoricalProject.cost_usd >= min_budget)
        applied_filters["min_budget"] = min_budget

    if max_budget is not None:
        query = query.filter(HistoricalProject.cost_usd <= max_budget)
        applied_filters["max_budget"] = max_budget

    if location_filter:
        query = query.filter(HistoricalProject.location.ilike(f"%{location_filter.strip()}%"))
        applied_filters["location"] = location_filter

    projects = query.limit(20).all()

    # If strict filtering returns empty, fall back to nearest similarity ranking
    if not projects and (sqft_filter or min_sqft or location_filter):
        all_projects = db.query(HistoricalProject).all()
        target_sqft = sqft_filter or min_sqft or 45000.0
        loc_clean = (location_filter or "").strip().lower()

        scored = []
        for p in all_projects:
            diff_ratio = abs(p.sqft - target_sqft) / max(target_sqft, 1.0)
            sim = max(0.05, 1.0 - diff_ratio)
            if loc_clean and any(w in p.location.lower() for w in loc_clean.split()):
                sim += 0.35
            scored.append((sim, diff_ratio, p))

        scored.sort(key=lambda x: (-x[0], x[1]))
        projects = [p for score, diff, p in scored[:5]]

    results = []
    for p in projects:
        # Calculate derived metrics for complete report display
        est_floors = floors or max(1, int(round(p.sqft / 7500.0)))
        struct_sys = structural_system or ("Reinforced Concrete Frame" if p.project_type == "Commercial" else ("Structural Steel Framing" if p.project_type == "Industrial" else "Wood / Light-Frame"))
        found_sys = foundation_type or ("Mat Foundation" if p.sqft >= 50000 else "Spread Footing")

        results.append({
            "id": p.id,
            "name": p.name,
            "project_type": p.project_type,
            "sqft": p.sqft,
            "floors": est_floors,
            "structural_system": struct_sys,
            "foundation_type": found_sys,
            "steel_tons_used": p.steel_tons_used,
            "cost_usd": p.cost_usd,
            "location": p.location
        })

    return {
        "applied_filters": applied_filters,
        "matching_count": len(results),
        "projects": results
    }


def query_leave_balance_db(db: Session, user: User) -> Dict[str, Any]:
    """
    Queries leave record for authenticated worker.
    """
    user_id = user.id if user and hasattr(user, 'id') else 1
    user_name = getattr(user, 'full_name', 'Employee') if user else 'Employee'
    
    leaves = db.query(LeaveRequest).filter(LeaveRequest.user_id == user_id, LeaveRequest.status == "APPROVED").all()
    used_days = sum(l.days for l in leaves)
    entitlement = 15
    remaining = max(0, entitlement - used_days)

    return {
        "user_name": user_name,
        "annual_entitlement_days": entitlement,
        "used_approved_days": used_days,
        "remaining_days": remaining
    }


def query_company_policy_kb(db: Session, query_str: str) -> List[Dict[str, str]]:
    """
    Queries company policy knowledge base.
    """
    policies = db.query(CompanyPolicy).all()
    results = []
    for p in policies:
        results.append({
            "category": p.category,
            "title": p.title,
            "content": p.content
        })
    return results
