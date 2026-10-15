import logging
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.auth import issue_token
from app.db import SessionDep
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


def _is_trusted(ip: str, networks: list[IPv4Network | IPv6Network]) -> bool:
    try:
        addr = ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def get_client_ip(request: Request) -> str:
    """IP do cliente, honrando X-Forwarded-For só quando vem de proxy confiável.

    Percorre o header da direita para a esquerda e devolve o primeiro hop que
    não é proxy confiável: os valores à esquerda dele são do cliente e podem
    ser forjados.
    """
    peer = request.client.host if request.client else "unknown"
    networks = [
        ip_network(p.strip(), strict=False)
        for p in get_settings().trusted_proxies.split(",")
        if p.strip()
    ]
    if not _is_trusted(peer, networks):
        return peer
    hops = [h.strip() for h in request.headers.get("X-Forwarded-For", "").split(",") if h.strip()]
    for hop in reversed(hops):
        if not _is_trusted(hop, networks):
            return hop
    return peer


def _require_admin(authorization: str = Header(...)) -> None:
    token = authorization.removeprefix("Bearer ")
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_public_key, algorithms=["RS256"], audience="automata"
        )
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
