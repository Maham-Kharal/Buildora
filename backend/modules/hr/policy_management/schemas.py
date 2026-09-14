from pydantic import BaseModel
from datetime import datetime

class CreatePolicySchema(BaseModel):
    title: str
    category: str
    content: str

class PolicyResponseSchema(BaseModel):
    id: int
    title: str
    category: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
