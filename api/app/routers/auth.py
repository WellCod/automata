import hashlib
import logging
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app import oidc
from app.auth import decode_token, issue_token
from app.db import SessionDep
from app.models.revoked_token import RevokedToken
from app.models.user import UserRole
from app.proxy import get_client_ip
from app.repositories.user import UserRepository
from app.schemas.user import (
    ROLE_SCOPES,
    CreateUserInput,
    LoginInput,
    TokenResponse,
    UserResponse,
)
from app.services.user import UserService
from app.settings import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)

_LOGIN_LIMIT_PER_IP = 20
# por e-mail e IP o limite padrão (5/min); só por e-mail, folgado: segura força bruta
# distribuída sem deixar qualquer um travar o login de outra pessoa com 5 tentativas
_LOGIN_LIMIT_PER_EMAIL = 30


def _email_ref(email: str) -> str:
    """Referência estável para o log sem gravar o e-mail digitado (que pode ser de outra pessoa)."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:12]


def _require_admin(authorization: str = Header(...)) -> None:
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Token inválido") from e
    if "agent_os:admin" not in payload.get("scopes", []):
        raise HTTPException(status_code=403, detail="Permissão insuficiente")


@router.post("/login", response_model=TokenResponse)
def login(request: Request, body: LoginInput, session: SessionDep) -> TokenResponse:
    ip = get_client_ip(request)
    email_ref = _email_ref(body.email)
    logger.info("login attempt", extra={"ip": ip, "email_ref": email_ref})
    # Por e-mail contra força bruta distribuída; por IP, com folga para vários
    # usuários atrás do mesmo NAT, contra varredura de contas
    limiter = request.app.state.rate_limiter
    limiter.check(f"login:ip:{ip}", limit=_LOGIN_LIMIT_PER_IP)
    email = body.email.lower()
    limiter.check(f"login:email:{email}:{ip}")
    limiter.check(f"login:email:{email}", limit=_LOGIN_LIMIT_PER_EMAIL)
    svc = UserService(UserRepository(session))
    try:
        user = svc.authenticate(body.email, body.password)
        user_id = str(user.id)
        user_role = user.role
        # sem login por senha, só o owner de emergência entra assim (ADR-0042)
        if not get_settings().password_login and user_role != UserRole.owner:
            raise ValueError("login por senha desligado")
        session.commit()
    except ValueError as e:
        session.rollback()
        logger.warning("login failed", extra={"ip": ip, "email_ref": email_ref})
        raise HTTPException(status_code=401, detail="Credenciais inválidas") from e
    logger.info("login ok", extra={"ip": ip, "user_id": user_id, "role": user_role})
    return TokenResponse(access_token=issue_token(user_id, ROLE_SCOPES[user_role]))


@router.post("/logout", status_code=204)
def logout(request: Request, session: SessionDep, authorization: str = Header(...)) -> Response:
    """Revoga o token da sessão: o RevocationMiddleware passa a recusá-lo até expirar."""
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Token inválido") from e
    jti = payload.get("jti")
    # token emitido antes do jti existir: não há o que revogar, expira sozinho
    if isinstance(jti, str):
        now = datetime.now(UTC)
        session.execute(
            insert(RevokedToken)
            .values(
                jti=jti,
                user_id=str(payload.get("sub", "")),
                expires_at=datetime.fromtimestamp(payload["exp"], UTC),
            )
            .on_conflict_do_nothing(index_elements=["jti"])
        )
        session.execute(delete(RevokedToken).where(RevokedToken.expires_at <= now))
        session.commit()
        request.app.state.revoked_tokens.revoke_now(jti)
        logger.info("logout", extra={"user_id": payload.get("sub")})
    return Response(status_code=204)


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    body: CreateUserInput,
    session: SessionDep,
    _: None = Depends(_require_admin),
) -> UserResponse:
    svc = UserService(UserRepository(session))
    try:
        user = svc.create_user(email=body.email, password=body.password, role=body.role)
        result = UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        session.commit()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return result


class OidcInfo(BaseModel):
    enabled: bool
    label: str
    password_login: bool


class OidcStart(BaseModel):
    url: str


class OidcCallback(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=64)


@router.get("/oidc", response_model=OidcInfo)
def oidc_info() -> OidcInfo:
    """O que a tela de login mostra; público, sem nada do provedor além do rótulo."""
    s = get_settings()
    return OidcInfo(enabled=oidc.enabled(), label=s.oidc_label, password_login=s.password_login)


@router.post("/oidc/start", response_model=OidcStart)
def oidc_start(request: Request, session: SessionDep) -> OidcStart:
    if not oidc.enabled():
        raise HTTPException(status_code=404, detail="SSO não configurado")
    request.app.state.rate_limiter.check(
        f"oidc:start:{get_client_ip(request)}", limit=_LOGIN_LIMIT_PER_IP
    )
    try:
        return OidcStart(url=oidc.start(session))
    except oidc.OidcError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/oidc/callback", response_model=TokenResponse)
def oidc_callback(request: Request, body: OidcCallback, session: SessionDep) -> TokenResponse:
    if not oidc.enabled():
        raise HTTPException(status_code=404, detail="SSO não configurado")
    ip = get_client_ip(request)
    request.app.state.rate_limiter.check(f"oidc:callback:{ip}", limit=_LOGIN_LIMIT_PER_IP)
    try:
        identity = oidc.finish(session, body.code, body.state)
    except oidc.OidcError as e:
        logger.warning("sso failed", extra={"ip": ip, "reason": str(e)})
        raise HTTPException(status_code=401, detail=str(e)) from e
    role = oidc.role_for(identity)
    if role is None:
        logger.warning("sso sem papel", extra={"ip": ip})
        raise HTTPException(status_code=403, detail="Seu grupo no provedor não dá acesso ao painel")
    if identity.email and not oidc.domain_allowed(identity.email):
        raise HTTPException(status_code=403, detail="Domínio de e-mail não autorizado")
    svc = UserService(UserRepository(session))
    try:
        user, cut = svc.sso_login(
            issuer=str(oidc.discovery()["issuer"]),
            subject=identity.subject,
            email=identity.email,
            email_verified=identity.email_verified,
            role=role,
        )
    except PermissionError as e:
        session.rollback()
        logger.warning("sso recusado", extra={"ip": ip, "reason": str(e)})
        raise HTTPException(status_code=403, detail=str(e)) from e
    if cut is not None:
        # o corte vale até o fim do segundo; o token novo sai no mesmo segundo
        cut = cut.replace(microsecond=0)
        user.tokens_valid_after = cut
    user_id, user_role = str(user.id), user.role
    session.commit()
    revoked = getattr(request.app.state, "revoked_tokens", None)
    if cut is not None and revoked is not None:
        revoked.cut_now(user_id, cut.timestamp())
    logger.info("sso ok", extra={"ip": ip, "user_id": user_id, "role": user_role})
    return TokenResponse(access_token=issue_token(user_id, ROLE_SCOPES[user_role]))
