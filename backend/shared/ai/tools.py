import re
import logging
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, or_
from backend.core.config import settings
from backend.db.models import Receipt, User, HistoricalProject, HistoricalProjectLevel, HistoricalSteelComponent, ActiveProject, LeaveRequest, CompanyPolicy

logger = logging.getLogger("buildora.tools")

def load_source_backed_historical_projects(db: Session) -> List[HistoricalProject]:
    """
    Loads all source-backed historical projects (data_quality != 'REFERENCE') with their
    levels and steel components using efficient selectinload to avoid N+1 queries.
    """
    return db.query(HistoricalProject).options(
        selectinload(HistoricalProject.levels),
        selectinload(HistoricalProject.steel_components)
    ).filter(HistoricalProject.data_quality != "REFERENCE").all()

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
        query = query.outerjoin(ActiveProject, Receipt.project_id == ActiveProject.id).filter(
            or_(
                ActiveProject.name.ilike(f"%{project_filter.strip()}%"),
                Receipt.vendor_name.ilike(f"%{project_filter.strip()}%")
            )
        )
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
        
        proj_name = (receipt.project.name if receipt.project else None) or receipt.vendor_name or "General Site Ops"
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
    building_type: Optional[str] = None,
    structural_system: Optional[str] = None,
    floors: Optional[int] = None,
    foundation_type: Optional[str] = None,
    floor_system: Optional[str] = None,
    min_steel_tons: Optional[float] = None,
    max_steel_tons: Optional[float] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    location_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Queries SQLite database for past structural projects using parameterized SQL filters:
    area (min/max), building type, steel tonnage, floors, structural system, foundation type, and location.
    Excludes REFERENCE dataset rows (P022) by default.
    """
    query = db.query(HistoricalProject).filter(HistoricalProject.data_quality != "REFERENCE")

    applied_filters = {}

    if min_sqft is not None:
        query = query.filter(HistoricalProject.total_covered_area_sqft >= min_sqft)
        applied_filters["min_sqft"] = min_sqft
    elif sqft_filter and sqft_filter > 0:
        query = query.filter(
            HistoricalProject.total_covered_area_sqft >= sqft_filter * 0.7,
            HistoricalProject.total_covered_area_sqft <= sqft_filter * 1.4
        )
        applied_filters["sqft_target"] = sqft_filter

    if max_sqft is not None:
        query = query.filter(HistoricalProject.total_covered_area_sqft <= max_sqft)
        applied_filters["max_sqft"] = max_sqft

    if building_type:
        query = query.filter(HistoricalProject.building_type.ilike(f"%{building_type.strip()}%"))
        applied_filters["building_type"] = building_type

    if structural_system:
        query = query.filter(
            or_(
                HistoricalProject.structural_system.ilike(f"%{structural_system.strip()}%"),
                HistoricalProject.building_type.ilike(f"%{structural_system.strip()}%"),
                HistoricalProject.project_title.ilike(f"%{structural_system.strip()}%")
            )
        )
        applied_filters["structural_system"] = structural_system

    if floors is not None:
        query = query.filter(HistoricalProject.above_ground_floors == floors)
        applied_filters["floors"] = floors

    if foundation_type:
        query = query.filter(HistoricalProject.foundation_type.ilike(f"%{foundation_type.strip()}%"))
        applied_filters["foundation_type"] = foundation_type

    if floor_system:
        query = query.filter(HistoricalProject.floor_system.ilike(f"%{floor_system.strip()}%"))
        applied_filters["floor_system"] = floor_system

    if min_steel_tons is not None:
        query = query.filter((HistoricalProject.total_rebar_net_lbs / 2000.0) >= min_steel_tons)
        applied_filters["min_steel_tons"] = min_steel_tons

    if max_steel_tons is not None:
        query = query.filter((HistoricalProject.total_rebar_net_lbs / 2000.0) <= max_steel_tons)
        applied_filters["max_steel_tons"] = max_steel_tons

    if location_filter:
        loc_clean = location_filter.strip()
        loc_lower = loc_clean.lower()
        state_map = {
            "california": "CA", "texas": "TX", "new york": "NY", "florida": "FL",
            "washington": "WA", "illinois": "IL", "georgia": "GA", "north carolina": "NC",
            "ohio": "OH", "virginia": "VA"
        }
        abbrev = state_map.get(loc_lower)
        if abbrev:
            query = query.filter(
                or_(
                    HistoricalProject.location.ilike(f"%{loc_clean}%"),
                    HistoricalProject.location.ilike(f"%, {abbrev}%"),
                    HistoricalProject.location.ilike(f"% {abbrev} %"),
                    HistoricalProject.location.ilike(f"% {abbrev}")
                )
            )
        else:
            query = query.filter(HistoricalProject.location.ilike(f"%{loc_clean}%"))
        applied_filters["location"] = location_filter

    projects = query.limit(20).all()

    results = []
    for p in projects:
        tons = round((p.total_rebar_net_lbs or 0.0) / 2000.0, 2)
        results.append({
            "id": p.id,
            "project_key": p.project_key,
            "name": p.project_title,
            "project_type": p.building_type,
            "sqft": p.total_covered_area_sqft,
            "total_rebar_net_lbs": p.total_rebar_net_lbs,
            "steel_tons_used": tons,
            "cost_usd": None,
            "location": p.location,
            "data_quality": p.data_quality
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


def query_company_policy_kb(db: Any = None, query_str: str = "") -> List[Dict[str, Any]]:
    """
    RAG-powered semantic search for company policies.
    Flow: query string -> generate query embedding -> search Qdrant -> relevance filtering -> return structured source chunks.
    Falls back to SQLite database keyword search if Qdrant yields no hits (e.g. in-memory or unindexed).
    Supports multi-topic queries (e.g. 'safety and expenses').
    """
    db_session = None
    if not isinstance(db, str) and db is not None:
        db_session = db
    elif isinstance(db, str) and not query_str:
        query_str = db

    query_str = (query_str or "").strip()
    if not query_str:
        logger.warning("POLICY_RETRIEVAL query is empty.")
        return []

    logger.info(f"POLICY_RETRIEVAL query received: '{query_str}'")

    # Multi-topic query splitting (e.g., "safety and expenses")
    sub_queries = [query_str]
    if " and " in query_str.lower() and not query_str.lower().startswith("what"):
        parts = [p.strip() for p in re.split(r'\band\b|,|;', query_str, flags=re.IGNORECASE) if len(p.strip()) > 2]
        if len(parts) > 1:
            sub_queries = parts

    all_sources: List[Dict[str, Any]] = []
    seen_keys = set()

    from backend.shared.ai.gemini import generate_embeddings
    from backend.shared.ai.qdrant import search_policy_chunks

    vector_search_failed = False
    for q in sub_queries:
        try:
            embeddings = generate_embeddings([q])
            if embeddings and len(embeddings) == 1:
                query_vector = embeddings[0]
                if len(query_vector) == settings.GEMINI_EMBEDDING_DIMENSION:
                    hits = search_policy_chunks(
                        query_vector=query_vector,
                        top_k=settings.POLICY_RETRIEVAL_TOP_K,
                        score_threshold=settings.POLICY_RETRIEVAL_SCORE_THRESHOLD
                    )
                    for h in hits:
                        key = (h.get("policy_document_id"), h.get("chunk_index"), h.get("text")[:50])
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_sources.append(h)
        except Exception as e:
            logger.error(f"POLICY_RETRIEVAL qdrant vector search error for '{q}': {e}")
            vector_search_failed = True

    # SQLite fallback: Trigger if vector search produced no results and db is provided
    if not all_sources and db_session is not None:
        try:
            logger.info("POLICY_RETRIEVAL falling back to SQLite database query...")
            policies = db_session.query(CompanyPolicy).all()
            q_lower = query_str.lower()
            stop_words = {"what", "where", "about", "tell", "show", "with", "from", "policy", "policies", "needed", "required", "does", "have", "are", "the", "for", "and"}
            keywords = [k for k in re.findall(r'\w+', q_lower) if len(k) > 3 and k not in stop_words]
            if not keywords:
                keywords = [q_lower]

            for p in policies:
                content_text = (p.content or "").strip()
                title_text = (p.title or "").strip()
                cat_text = (p.category or "").strip()
                filename_text = (p.original_filename or "").strip()
                combined_text = f"{title_text} {cat_text} {filename_text} {content_text}".lower()

                # Match if all specific non-generic keywords are present, or at least primary keyword
                if all(kw in combined_text for kw in keywords) or (len(keywords) > 1 and any(kw in combined_text for kw in keywords if kw not in ["leave", "work", "rule"])):
                    chunk_text = content_text if content_text else f"Policy: {title_text} (Category: {cat_text})"
                    all_sources.append({
                        "policy_document_id": p.id,
                        "title": title_text,
                        "category": cat_text,
                        "original_filename": filename_text or f"policy_{p.id}.txt",
                        "page_number": 1,
                        "chunk_index": 0,
                        "text": chunk_text,
                        "retrieval_score": 0.85
                    })
        except Exception as e:
            logger.error(f"POLICY_RETRIEVAL SQLite fallback query error: {e}")

    logger.info(f"POLICY_RETRIEVAL total relevant_chunks={len(all_sources)}")
    return all_sources
