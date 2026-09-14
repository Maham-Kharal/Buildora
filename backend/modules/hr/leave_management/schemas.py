from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class CreateLeaveRequestSchema(BaseModel):
    start_date: date
    end_date: date
    reason: str

class UpdateLeaveStatusSchema(BaseModel):
    status: str # APPROVED or REJECTED

class LeaveResponseSchema(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str]
    start_date: date
    end_date: date
    days: int
    reason: str
    status: str
    auto_approved: bool
    created_at: datetime

    class Config:
        from_attributes = True