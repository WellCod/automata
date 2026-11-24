import hashlib
import logging
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app import mailer, oidc
from app.auth import decode_token, issue_token
from app.db import SessionDep
from app.integrations import bearer_token
from app.models.revoked_token import RevokedToken
from app.models.user import UserRole
from app.proxy import known_client_ip
from app.repositories.user import UserRepository
from app.schemas.user import (
    ROLE_SCOPES,
    CreateUserInput,
    ForgotPasswordInput,
    LoginInput,
    ResetWithTokenInput,
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
    """Só deixa passar token com `agent_os:admin` (criação de usuário pela rota antiga)."""
    token = bearer_token(authorization)
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Token inválido") from exc
    if "agent_os:admin" not in payload.get("scopes", []):
        raise HTTPException(status_code=403, detail="Permissão insuficiente")


def _audit_login(
    request: Request, user_id: str | None, status: int, detail: dict[str, str]
) -> None:
    """Login entra na trilha pela rota, porque o middleware não sabe quem é antes (COM-07)."""
    from app.audit import record
    from app.logging_config import request_id_var

    try:
        record(
            actor=user_id,
            action="POST /api/v1/auth/login",
            params={},
            status_code=status,
            ip=known_client_ip(request),
            request_id=request_id_var.get(None),
            detail=detail,
        )
    except Exception as exc:
        logger.error("falha ao gravar login na trilha", extra={"error": str(exc)})


@router.post("/login", response_model=TokenResponse)
def login(request: Request, body: LoginInput, session: SessionDep) -> TokenResponse:
    """Login por e-mail e senha, com limite por IP e por e-mail e registro na trilha."""
    ip = known_client_ip(request)
    email_ref = _email_ref(body.email)
    logger.info("login attempt", extra={"ip": ip or "desconhecido", "email_ref": email_ref})
    # Por e-mail contra força bruta distribuída; por IP, com folga para vários
    # usuários atrás do mesmo NAT, contra varredura de contas. Sem o IP real, o
    # balde por IP seria um só para todos e fica de fora
    limiter = request.app.state.rate_limiter
    email = body.email.lower()
    if ip is not None:
        limiter.check(f"login:ip:{ip}", limit=_LOGIN_LIMIT_PER_IP)
        limiter.check(f"login:email:{email}:{ip}")
    limiter.check(f"login:email:{email}", limit=_LOGIN_LIMIT_PER_EMAIL)
    user_service = UserService(UserRepository(session))
    # A resposta de falha é a mesma para e-mail inexistente e senha errada; o
    # authenticate roda o argon2 nos dois casos para o tempo não denunciar a conta
    try:
        user = user_service.authenticate(body.email, body.password)
        user_id = str(user.id)
        user_role = user.role
        must_change_password = user.must_change_password
        # sem login por senha, só o owner de emergência entra assim (ADR-0042)
        if not get_settings().password_login and user_role != UserRole.owner:
            raise ValueError("login por senha desligado")
        session.commit()
    except ValueError as exc:
        logger.warning("login failed", extra={"ip": ip, "email_ref": email_ref})
        _audit_login(request, None, 401, {"email_ref": email_ref, "via": "senha"})
        raise HTTPException(status_code=401, detail="Credenciais inválidas") from exc
    logger.info("login ok", extra={"ip": ip, "user_id": user_id, "role": user_role})
    _audit_login(request, user_id, 200, {"via": "senha"})
    if must_change_password:
        # senha provisória: o token não tem scope, só serve para /me e /me/password
        return TokenResponse(
            access_token=issue_token(user_id, [], extra={"must_change_password": True}),
            must_change_password=True,
        )
    return TokenResponse(access_token=issue_token(user_id, ROLE_SCOPES[user_role]))


_RESET_SUBJECT = "Redefinição de senha do Automata"
_BAD_LINK = "Link inválido ou vencido. Peça outro."


@router.post("/password/forgot", status_code=202)
def forgot_password(request: Request, body: ForgotPasswordInput, session: SessionDep) -> Response:
    """Manda o link de redefinição. Responde igual exista ou não a conta."""
    ip = known_client_ip(request)
    limiter = request.app.state.rate_limiter
    email = body.email.lower()
    if ip is not None:
        limiter.check(f"password-forgot:ip:{ip}", limit=_LOGIN_LIMIT_PER_IP)
    limiter.check(f"password-forgot:email:{email}", limit=3)
    settings = get_settings()
    if not settings.password_login or not mailer.configured() or not settings.public_url:
        logger.warning("recuperação de senha sem SMTP, PUBLIC_URL ou login por senha")
        return Response(status_code=202)
    found = UserService(UserRepository(session)).request_reset(email, datetime.now(UTC))
    session.commit()
    if found is not None:
        user, token = found
        link = f"{settings.public_url.rstrip('/')}/redefinir-senha?token={token}"
        status = mailer.send(
            [user.email],
            _RESET_SUBJECT,
            "Alguém pediu para redefinir a senha desta conta no Automata.\n\n"
            f"Para escolher uma senha nova, abra o link em até 30 minutos:\n{link}\n\n"
            "Se não foi você, ignore este e-mail: a senha atual continua valendo.",
        )
        logger.info("link de senha", extra={"user_id": str(user.id), "status": status})
    return Response(status_code=202)


@router.post("/password/reset", response_model=TokenResponse)
def reset_password_with_token(
    request: Request, body: ResetWithTokenInput, session: SessionDep
) -> TokenResponse:
    """Troca a senha pelo link do e-mail e corta as sessões abertas antes da troca."""
    ip = known_client_ip(request)
    if ip is not None:
        request.app.state.rate_limiter.check(f"password-reset:ip:{ip}", limit=_LOGIN_LIMIT_PER_IP)
    try:
        user, sessions_cutoff = UserService(UserRepository(session)).reset_with_token(
            body.token, body.new_password, datetime.now(UTC)
        )
    except (ValueError, LookupError) as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=_BAD_LINK) from exc
    # o corte vale até o fim do segundo; o token novo sai no mesmo segundo
    sessions_cutoff = sessions_cutoff.replace(microsecond=0)
    user.tokens_valid_after = sessions_cutoff
    user_id, role = str(user.id), user.role
    session.commit()
    # avisa o cache de revogação deste processo na hora, sem esperar a recarga
    revoked_tokens = getattr(request.app.state, "revoked_tokens", None)
    if revoked_tokens is not None:
        revoked_tokens.cut_now(user_id, sessions_cutoff.timestamp())
    logger.info("senha redefinida pelo link", extra={"user_id": user_id})
    if not get_settings().password_login and role != UserRole.owner:
        # sem login por senha, só o owner entra assim (ADR-0042)
        raise HTTPException(status_code=403, detail="Login por senha desligado")
    return TokenResponse(access_token=issue_token(user_id, ROLE_SCOPES[role]))


@router.post("/logout", status_code=204)
def logout(request: Request, session: SessionDep, authorization: str = Header(...)) -> Response:
    """Revoga o token da sessão: o RevocationMiddleware passa a recusá-lo até expirar."""
    token = bearer_token(authorization)
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Token inválido") from exc
    jti = payload.get("jti")
    # token emitido antes do jti existir: não há o que revogar, expira sozinho
    if isinstance(jti, str):
        now = datetime.now(UTC)
        # grava a revogação e aproveita para limpar as que já expiraram
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
    """Cria usuário com senha provisória, que precisa ser trocada no primeiro acesso."""
    user_service = UserService(UserRepository(session))
    try:
        user = user_service.create_user(
            email=body.email, password=body.password, role=body.role, must_change=True
        )
        created_user = UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return created_user


class OidcInfo(BaseModel):
    enabled: bool
    label: str
    password_login: bool


class OidcStart(BaseModel):
    url: str


class OidcStartInput(BaseModel):
    # segredo do navegador, gerado pelo BFF e guardado só no cookie httpOnly
    browser_key: str = Field(min_length=32, max_length=128)


class OidcCallback(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=64)
    browser_key: str = Field(min_length=32, max_length=128)


@router.get("/oidc", response_model=OidcInfo)
def oidc_info() -> OidcInfo:
    """O que a tela de login mostra; público, sem nada do provedor além do rótulo."""
    settings = get_settings()
    return OidcInfo(
        enabled=oidc.enabled(), label=settings.oidc_label, password_login=settings.password_login
    )


@router.post("/oidc/start", response_model=OidcStart)
def oidc_start(request: Request, body: OidcStartInput, session: SessionDep) -> OidcStart:
    """Devolve a URL do provedor, com o state preso ao segredo do navegador."""
    if not oidc.enabled():
        raise HTTPException(status_code=404, detail="SSO não configurado")
    ip = known_client_ip(request)
    if ip is not None:
        request.app.state.rate_limiter.check(f"oidc:start:{ip}", limit=_LOGIN_LIMIT_PER_IP)
    try:
        return OidcStart(url=oidc.start(session, body.browser_key))
    except oidc.OidcError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/oidc/callback", response_model=TokenResponse)
def oidc_callback(request: Request, body: OidcCallback, session: SessionDep) -> TokenResponse:
    """Fecha o login por SSO: troca o código, confere papel e domínio e emite o token."""
    if not oidc.enabled():
        raise HTTPException(status_code=404, detail="SSO não configurado")
    ip = known_client_ip(request)
    if ip is not None:
        request.app.state.rate_limiter.check(f"oidc:callback:{ip}", limit=_LOGIN_LIMIT_PER_IP)
    try:
        identity = oidc.finish(session, body.code, body.state, body.browser_key)
    except oidc.OidcError as exc:
        logger.warning("sso failed", extra={"ip": ip, "reason": str(exc)})
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    role = oidc.role_for(identity)
    if role is None:
        logger.warning("sso sem papel", extra={"ip": ip})
        raise HTTPException(status_code=403, detail="Seu grupo no provedor não dá acesso ao painel")
    # domínio só vale com e-mail confirmado pelo provedor: num provedor com cadastro
    # aberto, qualquer um digita ceo@empresa.com (Fase 49)
    if oidc.domains_configured() and not (
        identity.email and identity.email_verified and oidc.domain_allowed(identity.email)
    ):
        raise HTTPException(status_code=403, detail="Domínio de e-mail não autorizado")
    user_service = UserService(UserRepository(session))
    try:
        # sessions_cutoff vem preenchido quando o papel mudou: as sessões antigas caem
        user, sessions_cutoff = user_service.sso_login(
            issuer=str(oidc.discovery()["issuer"]),
            subject=identity.subject,
            email=identity.email,
            email_verified=identity.email_verified,
            role=role,
        )
    except PermissionError as exc:
        session.rollback()
        logger.warning("sso recusado", extra={"ip": ip, "reason": str(exc)})
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if sessions_cutoff is not None:
        # o corte vale até o fim do segundo; o token novo sai no mesmo segundo
        sessions_cutoff = sessions_cutoff.replace(microsecond=0)
        user.tokens_valid_after = sessions_cutoff
    user_id, user_role = str(user.id), user.role
    session.commit()
    revoked_tokens = getattr(request.app.state, "revoked_tokens", None)
    if sessions_cutoff is not None and revoked_tokens is not None:
        revoked_tokens.cut_now(user_id, sessions_cutoff.timestamp())
    logger.info("sso ok", extra={"ip": ip, "user_id": user_id, "role": user_role})
    _audit_login(request, user_id, 200, {"via": "sso"})
    return TokenResponse(access_token=issue_token(user_id, ROLE_SCOPES[user_role]))


class InstanceInfo(BaseModel):
    """Marca e moeda da instância, públicas para a tela de login (COM-12, UX-08)."""

    app_name: str
    # só data URI de imagem: a CSP do painel não carrega imagem de outro domínio
    app_logo: str | None
    brl_per_usd: float | None


@router.get("/instance", response_model=InstanceInfo)
def instance_info() -> InstanceInfo:
    """Nome, logo e cotação da instância; logo fora de data URI cai no padrão."""
    settings = get_settings()
    logo = settings.app_logo_url.strip()
    if logo and not logo.startswith("data:image/"):
        logger.warning("APP_LOGO_URL precisa ser data:image/...; usando o logo padrão")
        logo = ""
    return InstanceInfo(
        app_name=settings.app_name.strip()[:40] or "automata",
        app_logo=logo or None,
        brl_per_usd=settings.brl_per_usd or None,
    )
