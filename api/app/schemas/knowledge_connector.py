"""Conectores de conhecimento (ADR-0024): configuração sem segredo e segredo à parte."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ConnectorKind = Literal["github", "s3", "sharepoint"]

_Path = Annotated[str, Field(default="", max_length=512)]


class GitHubSettings(BaseModel):
    repo: str = Field(pattern=r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$", max_length=200)
    branch: str = Field(default="main", min_length=1, max_length=200)
    path: _Path = ""
    # GitHub Enterprise; passa pelo filtro de saída como qualquer URL de fora
    api_url: str = Field(default="https://api.github.com", max_length=500)


class S3Settings(BaseModel):
    bucket: str = Field(min_length=3, max_length=63)
    region: str | None = Field(default=None, max_length=40)
    prefix: _Path = ""
    # MinIO e compatíveis; vazio = AWS
    endpoint_url: str | None = Field(default=None, max_length=500)


class SharePointSettings(BaseModel):
    hostname: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9.\-]+$")
    site_path: str = Field(min_length=1, max_length=255)
    folder_path: _Path = ""
    tenant_id: str = Field(min_length=1, max_length=100)
    client_id: str = Field(min_length=1, max_length=100)


SETTINGS_BY_KIND: dict[str, type[BaseModel]] = {
    "github": GitHubSettings,
    "s3": S3Settings,
    "sharepoint": SharePointSettings,
}

# campos do segredo por tipo; GitHub sem token lê repositório público e S3 sem chave
# usa a credencial da instância (papel da máquina)
SECRET_FIELDS: dict[str, tuple[str, ...]] = {
    "github": ("token",),
    "s3": ("access_key_id", "secret_access_key"),
    "sharepoint": ("client_secret",),
}
SECRET_REQUIRED: dict[str, bool] = {"github": False, "s3": False, "sharepoint": True}


class ConnectorInput(BaseModel):
    kind: ConnectorKind
    name: str = Field(min_length=1, max_length=255)
    settings: dict[str, Any]
    # None mantém o segredo salvo; {} apaga
    secret: dict[str, Annotated[str, Field(max_length=4000)]] | None = None


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
    content_count: int
    created_by: str
    created_at: datetime


class ConnectorTestResult(BaseModel):
    ok: bool
    files: int
    sample: list[str]
    error: str | None
