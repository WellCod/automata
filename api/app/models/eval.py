import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class EvalCase(Base):
    """Caso de teste de agente ou time (ADR-0015), fora da versão: o rascunho não mexe no teste."""

    __tablename__ = "eval_case"
    __table_args__ = (UniqueConstraint("agent_config_id", "name", name="uq_eval_case_nome"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_config.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    # mensagens anteriores, rodadas na mesma sessão antes de `input` (ADR-0016)
    context: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # lista de checagens validada por EvalCaseInput (texto, tools, juiz)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # run de conversa de onde o caso veio, quando veio de "Virar caso de teste"
    source_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EvalRun(Base):
    """Execução da suíte contra uma versão exata do agente ou time."""

    __tablename__ = "eval_run"
    __table_args__ = (
        Index("ix_eval_run_config_created", "agent_config_id", "created_at"),
        Index("ix_eval_run_version", "version_id"),
        Index("ix_eval_run_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_config.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_config_version.id"), nullable=False
    )
    # queued → running → completed | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # caso cujas checagens não puderam rodar (juiz no modo demo, por exemplo)
    not_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # soma do usage_event da execução: casos e juiz
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float | None] = mapped_column(Numeric(14, 8), nullable=True)
    # cópia dos casos como estavam: o resultado continua legível depois de editar o caso
    cases: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    started_by: Mapped[str] = mapped_column(String(255), nullable=False)
    # manual (painel) | integration (token de consumidor) | schedule
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, server_default="manual")
    # draft | current quando o alvo veio por apelido; nulo quando veio por version_id
    target: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvalResult(Base):
    __tablename__ = "eval_result"
    __table_args__ = (Index("ix_eval_result_run", "eval_run_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_run.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_case.id", ondelete="SET NULL"), nullable=True
    )
    case_name: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # passed | failed | error | not_evaluated
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # uma entrada por checagem: tipo, se passou e o detalhe (regra, tools, motivo do juiz)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    tools_called: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvalSchedule(Base):
    """Agendamento da suíte de um config (ADR-0016): um por config, rodado pelo poller da API."""

    __tablename__ = "eval_schedule"
    __table_args__ = (Index("ix_eval_schedule_due", "enabled", "next_run_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_config.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    # current por padrão: o agendamento acompanha a vigente depois de cada publicação
    target: Mapped[str] = mapped_column(String(16), nullable=False, server_default="current")
    judge_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_run.id", ondelete="SET NULL"), nullable=True
    )
    # por que o último horário não virou execução (já rodando, sem casos, sem juiz)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
