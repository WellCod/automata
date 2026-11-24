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
    # sem sessions:read e traces:read: o viewer vê métricas e execuções, não o conteúdo
    # das conversas, que é dado pessoal (COM-09)
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
        Scope.CONVERSATIONS_HANDLE,
    ],
    UserRole.viewer: _VIEWER_SCOPES,
}


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


def _password_complexity(password: str) -> str:
    """Regra comum a toda senha nova; o tamanho mínimo fica no `Field` de cada schema."""
    if not any(char.isupper() for char in password):
        raise ValueError("a senha deve conter ao menos uma letra maiúscula")
    if not any(char.isdigit() for char in password):
        raise ValueError("a senha deve conter ao menos um dígito")
    return password


class CreateUserInput(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def email_minusculo(cls, email: str) -> str:
        return email.lower()

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
    # o token só serve para trocar a senha provisória (ADR-0045)
    must_change_password: bool = False


class ChangePasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _password_complexity(v)


class ForgotPasswordInput(BaseModel):
    email: EmailStr


class ResetWithTokenInput(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=12, max_length=256)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _password_complexity(v)


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None
    # conta que entra pelo SSO (ADR-0042)
    sso: bool = False


class MeResponse(BaseModel):
    id: str
    email: str | None
    role: UserRole | None
    # o painel esconde o que o papel não permite (UX-06)
    scopes: list[str] = []
