import logging
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.auth import decode_token, issue_token
from app.db import SessionDep
from app.models.revoked_token import RevokedToken
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

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)

_LOGIN_LIMIT_PER_IP = 20


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
    logger.info("login attempt", extra={"ip": ip, "email": body.email})
    # Por e-mail contra força bruta distribuída; por IP, com folga para vários
    # usuários atrás do mesmo NAT, contra varredura de contas
    limiter = request.app.state.rate_limiter
    limiter.check(f"login:ip:{ip}", limit=_LOGIN_LIMIT_PER_IP)
    limiter.check(f"login:email:{body.email.lower()}")
    svc = UserService(UserRepository(session))
    try:
        user = svc.authenticate(body.email, body.password)
        user_id = str(user.id)
        user_role = user.role
        session.commit()
    except ValueError as e:
        logger.warning("login failed", extra={"ip": ip, "email": body.email})
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
