from pydantic import BaseModel
from typing import List, Optional

class ProjectMemberOut(BaseModel):
    user_id: int
    full_name: str
    email: str
    role: str

    class Config:
        from_attributes = True

class AssignableUserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True

class ProjectCreate(BaseModel):
    name: str
    location: str
    sqft: float
    floors: int
    structural_system: str
    member_ids: List[int] = []

class ProjectOut(BaseModel):
    id: int
    name: str
    location: str
    sqft: float
    floors: int
    structural_system: str
    members: List[ProjectMemberOut]
    status: str

    class Config:
        from_attributes = True

