import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class UserRole(enum.StrEnum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"


class User(Base):
    __tablename__ = "user_account"
    __table_args__ = (UniqueConstraint("sso_issuer", "sso_subject", name="uq_user_account_sso"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # vazio na conta criada pelo SSO (ADR-0042)
    hashed_password: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sso_issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sso_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="userrole"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # tokens emitidos antes disto são recusados: desativar, trocar papel ou senha
    # derruba as sessões abertas na hora, sem esperar a expiração de 1 h
    tokens_valid_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
