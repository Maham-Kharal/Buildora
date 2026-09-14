from pydantic import BaseModel, EmailStr
from datetime import datetime

class CreateUserSchema(BaseModel):
    email: EmailStr
    full_name: str
    role: str # WORKER, ADMIN, HR_MANAGER
    password: str

class ResetPasswordSchema(BaseModel):
    new_password: str

class UserResponseSchema(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Aliases to guarantee compatibility across schema naming conventions
UserCreateRequest = CreateUserSchema
PasswordResetRequest = ResetPasswordSchema
