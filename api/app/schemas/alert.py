from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

AlertEvent = Literal[
    "budget.warning",
    "budget.exceeded",
    "caller_budget.warning",
    "caller_budget.exceeded",
    "errors.spike",
    "suite.regressed",
    "suite.failing",
    "suite.recovered",
    # pedidos do titular (ADR-0036)
    "data_subject.failed",
    "data_subject.due",
    # run em background que falhou de vez (ADR-0037)
    "job.failed",
    # custo estimado longe do informado pelo provedor num dia fechado (ADR-0037)
    "cost.divergence",
]


class AlertDestinationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    kind: Literal["webhook", "email"] = "webhook"
    url: str | None = Field(default=None, min_length=8, max_length=2000)
    # só no tipo e-mail (ADR-0037)
    emails: list[EmailStr] = Field(default_factory=list, max_length=5)
    events: list[AlertEvent] = Field(min_length=1)

    @model_validator(mode="after")
    def destino_do_tipo(self) -> "AlertDestinationCreate":
        if self.kind == "webhook" and not self.url:
            raise ValueError("o webhook precisa da URL")
        if self.kind == "email" and not self.emails:
            raise ValueError("o destino por e-mail precisa de ao menos um endereço")
        return self


class AlertDestinationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    events: list[AlertEvent] = Field(min_length=1)


class AlertDestinationResponse(BaseModel):
    id: UUID
    name: str
    kind: str = "webhook"
    # só o host sai da API: URL de Slack e Teams carrega token
    host: str
    emails: list[str] = []
    events: list[AlertEvent]
    created_by: str
    last_status: str | None
    last_at: datetime | None
    created_at: datetime


class AlertDestinationIssued(AlertDestinationResponse):
    # mostrado uma vez: confere a assinatura X-Automata-Signature (HMAC-SHA256 do corpo);
    # vazio no tipo e-mail
    secret: str


class AlertChannels(BaseModel):
    webhook: bool = True
    # SMTP_HOST no ambiente da API
    email: bool


class AlertTestResult(BaseModel):
    status: str
    delivered: bool
