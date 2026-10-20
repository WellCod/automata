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
    "workflows:read",
    "sessions:read",
    "traces:read",
    Scope.CONFIGS_READ,
    Scope.METRICS_READ,
    Scope.MCP_SERVERS_READ,
    Scope.KNOWLEDGE_READ,
    Scope.EVALS_READ,
]

ROLE_SCOPES: dict[UserRole, list[str]] = {
    UserRole.owner: ["agent_os:admin"],
    UserRole.editor: [
        *_VIEWER_SCOPES,
        "agents:run",
        "teams:run",
        "workflows:run",
        "sessions:write",
        Scope.CONFIGS_WRITE,
        Scope.CONFIGS_PUBLISH,
        Scope.KNOWLEDGE_WRITE,
        Scope.EVALS_WRITE,
        Scope.EVALS_RUN,
    ],
    UserRole.viewer: _VIEWER_SCOPES,
}


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


def _password_complexity(v: str) -> str:
    if not any(c.isupper() for c in v):
        raise ValueError("a senha deve conter ao menos uma letra maiúscula")
    if not any(c.isdigit() for c in v):
        raise ValueError("a senha deve conter ao menos um dígito")
    return v


class CreateUserInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    role: UserRole = UserRole.viewer

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _password_complexity(v)


class UpdateUserInput(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class ResetPasswordInput(BaseModel):
    password: str = Field(min_length=12)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _password_complexity(v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class MeResponse(BaseModel):
    id: str
    email: str | None
    role: UserRole | None
