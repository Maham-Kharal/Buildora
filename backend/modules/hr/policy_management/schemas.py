from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PolicyDocumentOut(BaseModel):
    id: int
    title: str
    category: str
    content: Optional[str] = None
    original_filename: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    uploaded_by: Optional[int] = None
    index_status: Optional[str] = "UPLOADED"
    chunk_count: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True

# Backwards compatibility alias
PolicyResponseSchema = PolicyDocumentOut
