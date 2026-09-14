from pydantic import BaseModel

class HRAssistantQuerySchema(BaseModel):
    prompt: str

class HRAssistantResponseSchema(BaseModel):
    answer: str
    auto_approved_leave: bool
