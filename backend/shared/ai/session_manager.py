import time
from typing import Dict, Any, Optional

class SessionManager:
    """
    In-memory session state manager for Buildora AI Assistant.
    Maintains multi-turn conversational context for:
    1. Steel takeoff slot filling
    2. Dynamic past project database filters
    3. Dynamic financial expense report filters
    """
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def _default_steel_context(self) -> Dict[str, Any]:
        return {
            "total_covered_area_sqft": None,
            "building_type": None,
            "basement_count": None,
            "above_ground_floors": None,
            "structural_system": None,
            "foundation_type": None,
            "floor_system": None,
            "location": None,
            "steel_grade": "Grade 60",
            "active": False,
            "awaiting_slot": None,
        }

    def _default_project_filter_context(self) -> Dict[str, Any]:
        return {
            "min_sqft": None,
            "max_sqft": None,
            "structural_system": None,
            "floors": None,
            "foundation_type": None,
            "min_steel_tons": None,
            "max_steel_tons": None,
            "min_budget": None,
            "max_budget": None,
            "location": None,
            "active": False,
        }

    def _default_expense_filter_context(self) -> Dict[str, Any]:
        return {
            "start_date": None,
            "end_date": None,
            "date_label": None,
            "category": None,
            "worker_name": None,
            "project_name": None,
            "min_amount": None,
            "max_amount": None,
            "active": False,
        }

    def get_session(self, session_id: str) -> Dict[str, Any]:
        if not session_id:
            return {}
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "created_at": time.time(),
                "last_active": time.time(),
                "steel_context": self._default_steel_context(),
                "project_filter_context": self._default_project_filter_context(),
                "expense_filter_context": self._default_expense_filter_context(),
                "last_intent": None
            }
        else:
            self._sessions[session_id]["last_active"] = time.time()
        return self._sessions[session_id]

    # ── Steel Estimation Session Management ──────────────────────────────────
    def set_awaiting_slot(self, session_id: str, slot_name: str):
        session = self.get_session(session_id)
        session["steel_context"]["awaiting_slot"] = slot_name

    def get_awaiting_slot(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        return session.get("steel_context", {}).get("awaiting_slot")

    def update_steel_context(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        session = self.get_session(session_id)
        steel = session.setdefault("steel_context", self._default_steel_context())
        for k, v in updates.items():
            if v is not None:
                steel[k] = v
        steel["active"] = True
        return steel

    def clear_steel_context(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id]["steel_context"] = self._default_steel_context()

    def mark_steel_active(self, session_id: str):
        session = self.get_session(session_id)
        session["steel_context"]["active"] = True

    # ── Past Project Filters Session Management ─────────────────────────────
    def get_project_filter_context(self, session_id: str) -> Dict[str, Any]:
        session = self.get_session(session_id)
        return session.setdefault("project_filter_context", self._default_project_filter_context())

    def update_project_filter_context(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        session = self.get_session(session_id)
        filters = session.setdefault("project_filter_context", self._default_project_filter_context())
        for k, v in updates.items():
            if v is not None:
                filters[k] = v
        filters["active"] = True
        return filters

    def clear_project_filter_context(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id]["project_filter_context"] = self._default_project_filter_context()

    # ── Expense Filters Session Management ───────────────────────────────────
    def get_expense_filter_context(self, session_id: str) -> Dict[str, Any]:
        session = self.get_session(session_id)
        return session.setdefault("expense_filter_context", self._default_expense_filter_context())

    def update_expense_filter_context(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        session = self.get_session(session_id)
        filters = session.setdefault("expense_filter_context", self._default_expense_filter_context())
        for k, v in updates.items():
            if v is not None:
                filters[k] = v
        filters["active"] = True
        return filters

    def clear_expense_filter_context(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id]["expense_filter_context"] = self._default_expense_filter_context()


session_manager = SessionManager()
