import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

_SLUG = r"^[a-z][a-z0-9_]{1,30}$"
_HEADER = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class McpServerInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=_SLUG, description="Prefixo das tools deste servidor")
    url: HttpUrl
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    # None mantém os headers salvos; {} apaga. Valores nunca voltam na resposta.
    headers: dict[str, str] | None = None

    @field_validator("headers")
    @classmethod
    def header_names_validos(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is not None:
            for name in v:
                if not _HEADER.match(name):
                    raise ValueError(f"nome de header inválido: {name}")
        return v


class McpToolInfo(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)


class McpServerResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    url: str
    timeout_seconds: int
    header_names: list[str]
    tools: list[McpToolInfo] | None
    tools_discovered_at: datetime | None
    updated_by: str
    created_at: datetime
    updated_at: datetime
