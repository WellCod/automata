from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole

ROLE_SCOPES: dict[UserRole, list[str]] = {
    UserRole.owner: ["agent_os:admin"],
    UserRole.editor: ["agent_os:write"],
    UserRole.viewer: ["agent_os:read"],
}


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class CreateUserInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    role: UserRole = UserRole.viewer

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("a senha deve conter ao menos uma letra maiúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("a senha deve conter ao menos um dígito")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
