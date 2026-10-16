from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.authz import Scope
from app.models.user import UserRole

# Scopes do AgentOS seguem o mapa padrão do Agno (agno.os.scopes); os de
# configs e metrics são das rotas próprias (app.authz). Tabela em api/README.md.
_VIEWER_SCOPES = [
    "agents:read",
    "teams:read",
    "sessions:read",
    "traces:read",
    Scope.CONFIGS_READ,
    Scope.METRICS_READ,
    Scope.MCP_SERVERS_READ,
    Scope.KNOWLEDGE_READ,
]

ROLE_SCOPES: dict[UserRole, list[str]] = {
    UserRole.owner: ["agent_os:admin"],
    UserRole.editor: [
        *_VIEWER_SCOPES,
        "agents:run",
        "teams:run",
        "sessions:write",
        Scope.CONFIGS_WRITE,
        Scope.CONFIGS_PUBLISH,
        Scope.KNOWLEDGE_WRITE,
    ],
    UserRole.viewer: _VIEWER_SCOPES,
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
