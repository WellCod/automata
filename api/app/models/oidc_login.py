from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class OidcLogin(Base):
    """Login por SSO em andamento (ADR-0042): uso único, vale 10 minutos."""

    __tablename__ = "oidc_login"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    # sha256 do segredo que só o navegador que começou tem (cookie httpOnly); o state
    # vai na URL e sozinho não prende o login a ninguém (Fase 49)
    browser_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
