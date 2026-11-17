"""Modelos de agente prontos para a instância vazia (UX-02).

Os mesmos agentes do seed da demo, sem o resto da demo: o primeiro agente sai com
instruções de exemplo e só falta testar. O rascunho passa pelos padrões seguros da
criação (ADR-0045), porque o payload do exemplo não traz guardrails nem controle do run.
"""

import re
import unicodedata
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.repositories.config import ConfigRepository
from app.schemas.config import ConfigKind, ConfigPayload
from app.services.config import ConfigService

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


class AgentTemplate(BaseModel):
    key: str
    name: str
    description: str
    model_id: str


class CreatedFromTemplate(BaseModel):
    id: UUID


def _key(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def _templates() -> dict[str, dict[str, Any]]:
    from app.seed import _DEMO_AGENTS

    return {_key(a["name"]): a for a in _DEMO_AGENTS}


@router.get(
    "",
    response_model=list[AgentTemplate],
    dependencies=[Depends(require_scopes(Scope.CONFIGS_READ))],
)
def list_templates() -> list[AgentTemplate]:
    return [
        AgentTemplate(
            key=key,
            name=a["name"],
            description=a["description"],
            model_id=a["payload"].model_id or "",
        )
        for key, a in _templates().items()
    ]


@router.post(
    "/{key}",
    response_model=CreatedFromTemplate,
    status_code=201,
    dependencies=[Depends(require_scopes(Scope.CONFIGS_WRITE))],
)
def create_from_template(key: str, session: SessionDep, request: Request) -> CreatedFromTemplate:
    template = _templates().get(key)
    if template is None:
        raise HTTPException(status_code=404, detail="Modelo de agente não encontrado")
    service = ConfigService(ConfigRepository(session))
    config = service.create_config(
        template["name"], description=template["description"], kind=ConfigKind.agent
    )
    payload: ConfigPayload = template["payload"]
    # cópia sem os campos marcados como enviados: o primeiro rascunho ganha as defesas
    fresh = ConfigPayload.model_validate(payload.model_dump(exclude={"guardrails", "run"}))
    author = str(getattr(request.state, "user_id", None) or "panel")
    service.save_draft(config.id, fresh, author)
    session.commit()
    return CreatedFromTemplate(id=config.id)
