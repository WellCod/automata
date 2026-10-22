from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AlertEvent = Literal[
    "budget.warning",
    "budget.exceeded",
    "errors.spike",
    "suite.regressed",
    "suite.failing",
    "suite.recovered",
]


class AlertDestinationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=8, max_length=2000)
    events: list[AlertEvent] = Field(min_length=1)


class AlertDestinationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    events: list[AlertEvent] = Field(min_length=1)


class AlertDestinationResponse(BaseModel):
    id: UUID
    name: str
    # só o host sai da API: URL de Slack e Teams carrega token
    host: str
    events: list[AlertEvent]
    created_by: str
    last_status: str | None
    last_at: datetime | None
    created_at: datetime


class AlertDestinationIssued(AlertDestinationResponse):
    # mostrado uma vez: confere a assinatura X-Automata-Signature (HMAC-SHA256 do corpo)
    secret: str


class AlertTestResult(BaseModel):
    status: str
    delivered: bool
