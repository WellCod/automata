import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.schemas.config import ConfigPayloadStatus


class Base(DeclarativeBase):
    pass


class AgentConfigVersion(Base):
    __tablename__ = "agent_config_version"
    __table_args__ = (
        Index("ix_agent_config_version_config_id_version_number", "config_id", "version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_config.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ConfigPayloadStatus] = mapped_column(
        Enum(ConfigPayloadStatus), nullable=False, default=ConfigPayloadStatus.draft
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[type-arg]
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    config: Mapped["AgentConfig"] = relationship(
        "AgentConfig", foreign_keys=[config_id], back_populates="versions"
    )


class AgentConfig(Base):
    __tablename__ = "agent_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_config_version.id", use_alter=True, name="fk_current_version"),
        nullable=True,
    )
    draft_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_config_version.id", use_alter=True, name="fk_draft_version"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )

    versions: Mapped[list[AgentConfigVersion]] = relationship(
        "AgentConfigVersion",
        foreign_keys="AgentConfigVersion.config_id",
        back_populates="config",
    )
    current_version: Mapped[AgentConfigVersion | None] = relationship(
        "AgentConfigVersion", foreign_keys=[current_version_id]
    )
    draft_version: Mapped[AgentConfigVersion | None] = relationship(
        "AgentConfigVersion", foreign_keys=[draft_version_id]
    )
