import time
from collections import defaultdict
from threading import Lock

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

_login_attempts: dict[str, list[float]] = defaultdict(list)
_lock = Lock()
_RATE_WINDOW = 60
_RATE_LIMIT = 5


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    with _lock:
        attempts = _login_attempts[ip]
        _login_attempts[ip] = [t for t in attempts if now - t < _RATE_WINDOW]
        if len(_login_attempts[ip]) >= _RATE_LIMIT:
            raise HTTPException(
                status_code=429, detail="Muitas tentativas. Tente novamente em breve."
            )
        _login_attempts[ip].append(now)


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
def login(
    request: Request, body: LoginInput, session: SessionDep
) -> TokenResponse:
    ip = get_client_ip(request)
    _check_rate_limit(ip)
    svc = UserService(UserRepository(session))
    try:
        user = svc.authenticate(body.email, body.password)
        user_id = str(user.id)
        user_role = user.role
        session.commit()
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Credenciais inválidas") from e
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
