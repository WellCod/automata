"""Conectores de conhecimento (ADR-0024): configuração sem segredo e segredo à parte."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ConnectorKind = Literal["github", "s3", "sharepoint", "gdrive", "gcs"]

_Path = Annotated[str, Field(default="", max_length=512)]


class PathFilters(BaseModel):
    """Glob sobre o caminho relativo (ADR-0039): sem include entra tudo, exclude vence."""

    include: list[str] = Field(default_factory=list, max_length=10)
    exclude: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("include", "exclude")
    @classmethod
    def padroes_validos(cls, value: list[str]) -> list[str]:
        from app.knowledge.path_filter import pattern_problem

        cleaned = [p.strip() for p in value if p.strip()]
        for pattern in cleaned:
            problem = pattern_problem(pattern)
            if problem:
                raise ValueError(f"{problem}: {pattern!r}")
        return cleaned


class GitHubSettings(PathFilters):
    repo: str = Field(pattern=r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$", max_length=200)
    branch: str = Field(default="main", min_length=1, max_length=200)
    path: _Path = ""
    # GitHub Enterprise; passa pelo filtro de saída como qualquer URL de fora
    api_url: str = Field(default="https://api.github.com", max_length=500)


class S3Settings(PathFilters):
    bucket: str = Field(min_length=3, max_length=63)
    region: str | None = Field(default=None, max_length=40)
    prefix: _Path = ""
    # MinIO e compatíveis; vazio = AWS
    endpoint_url: str | None = Field(default=None, max_length=500)


class SharePointSettings(PathFilters):
    hostname: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9.\-]+$")
    site_path: str = Field(min_length=1, max_length=255)
    folder_path: _Path = ""
    tenant_id: str = Field(min_length=1, max_length=100)
    client_id: str = Field(min_length=1, max_length=100)


class GDriveSettings(PathFilters):
    """Pasta do Google Drive (ADR-0039); compartilhe só ela com a conta de serviço."""

    folder_id: str = Field(min_length=10, max_length=100, pattern=r"^[A-Za-z0-9_\-]+$")
    shared_drive: bool = False


class GCSSettings(PathFilters):
    bucket: str = Field(min_length=3, max_length=222, pattern=r"^[a-z0-9][a-z0-9._\-]+$")
    prefix: _Path = ""


SETTINGS_BY_KIND: dict[str, type[BaseModel]] = {
    "github": GitHubSettings,
    "s3": S3Settings,
    "sharepoint": SharePointSettings,
    "gdrive": GDriveSettings,
    "gcs": GCSSettings,
}

# campos do segredo por tipo; GitHub sem token lê repositório público e S3 sem chave
# usa a credencial da instância (papel da máquina)
SECRET_FIELDS: dict[str, tuple[str, ...]] = {
    "github": ("token",),
    "s3": ("access_key_id", "secret_access_key"),
    "sharepoint": ("client_secret",),
    # o JSON inteiro da chave da conta de serviço (ADR-0039)
    "gdrive": ("service_account_json",),
    "gcs": ("service_account_json",),
}
SECRET_REQUIRED: dict[str, bool] = {
    "github": False,
    "s3": False,
    "sharepoint": True,
    "gdrive": True,
    "gcs": True,
}


class ConnectorInput(BaseModel):
    kind: ConnectorKind
    name: str = Field(min_length=1, max_length=255)
    settings: dict[str, Any]
    # None mantém o segredo salvo; {} apaga
    secret: dict[str, Annotated[str, Field(max_length=8000)]] | None = None
    # vazio = só manual
    sync_every_hours: int | None = Field(default=None, ge=1, le=168)


class ConnectorResponse(BaseModel):
    id: UUID
    base_id: UUID
    kind: ConnectorKind
    name: str
    settings: dict[str, Any]
    # nunca o segredo: só se há um salvo
    has_secret: bool
    last_status: str
    last_message: str | None
    last_summary: dict[str, Any] | None
    last_sync_at: datetime | None
    sync_every_hours: int | None
    next_sync_at: datetime | None
    content_count: int
    created_by: str
    created_at: datetime


class ConnectorTestResult(BaseModel):
    ok: bool
    files: int
    sample: list[str]
    error: str | None
