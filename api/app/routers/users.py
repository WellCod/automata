"""Gestão de usuários da instância (só owner) e o usuário logado (/me)."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.audit import note
from app.auth import issue_token
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import (
    ROLE_SCOPES,
    ChangePasswordInput,
    CreateUserInput,
    MeResponse,
    ResetPasswordInput,
    TokenResponse,
    UpdateUserInput,
    UserResponse,
)
from app.services.user import ConflictError, UserService

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    dependencies=[Depends(require_scopes(Scope.USERS_ADMIN))],
)
me_router = APIRouter(prefix="/api/v1/me", tags=["users"])
logger = logging.getLogger(__name__)


def to_response(u: User) -> UserResponse:
    return UserResponse(
        id=u.id,
        email=u.email,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
        sso=u.sso_subject is not None,
    )


def _actor(request: Request) -> str | None:
    """Id de quem fez a requisição, ou None sem usuário no token."""
    user_id = getattr(request.state, "user_id", None)
    return str(user_id) if user_id else None


def _cut(request: Request, user: User, cutoff: datetime | None) -> None:
    """Recusa os tokens do usuário emitidos antes de `cutoff`."""
    # vale já neste processo; os outros workers pegam no próximo refresh (30 s)
    revoked_tokens = getattr(request.app.state, "revoked_tokens", None)
    if cutoff is not None and revoked_tokens is not None:
        revoked_tokens.cut_now(str(user.id), cutoff.timestamp())


@me_router.get("", response_model=MeResponse)
def me(request: Request, session: SessionDep) -> MeResponse:
    """Quem está logado. Token de integração não tem usuário: volta só o sub."""
    subject = _actor(request) or ""
    try:
        user = UserRepository(session).get(UUID(subject))
    except ValueError:
        user = None
    scopes = [str(scope) for scope in getattr(request.state, "scopes", None) or []]
    if user is None:
        return MeResponse(id=subject, email=None, role=None, scopes=scopes)
    return MeResponse(id=str(user.id), email=user.email, role=user.role, scopes=scopes)


@me_router.post("/password", response_model=TokenResponse)
def change_own_password(
    body: ChangePasswordInput, session: SessionDep, request: Request
) -> TokenResponse:
    """Troca pela própria pessoa. Corta as outras sessões e devolve o token novo."""
    subject = _actor(request) or ""
    # token de integração tem sujeito `integration:<id>`, que não é UUID
    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Só usuário do painel troca senha") from exc
    request.app.state.rate_limiter.check(f"password-change:{subject}", limit=5)
    try:
        user, sessions_cutoff = UserService(UserRepository(session)).change_own_password(
            user_id, body.current_password, body.new_password
        )
    except LookupError as exc:
        raise HTTPException(status_code=403, detail="Só usuário do painel troca senha") from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # o corte vale até o fim do segundo; o token novo sai no mesmo segundo
    sessions_cutoff = sessions_cutoff.replace(microsecond=0)
    user.tokens_valid_after = sessions_cutoff
    role = user.role
    session.commit()
    _cut(request, user, sessions_cutoff)
    logger.info("senha trocada pelo usuário", extra={"user_id": subject})
    return TokenResponse(access_token=issue_token(subject, ROLE_SCOPES[role]))


@router.get("", response_model=list[UserResponse])
def list_users(session: SessionDep) -> list[UserResponse]:
    return [to_response(user) for user in UserRepository(session).list_all()]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(body: CreateUserInput, session: SessionDep, request: Request) -> UserResponse:
    """Cria usuário com senha provisória, que precisa ser trocada no primeiro acesso."""
    try:
        user = UserService(UserRepository(session)).create_user(
            email=body.email, password=body.password, role=body.role, must_change=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    session.refresh(user)
    logger.info(
        "usuário criado",
        extra={"user_id": str(user.id), "role": user.role, "by": _actor(request)},
    )
    return to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID, body: UpdateUserInput, session: SessionDep, request: Request
) -> UserResponse:
    """Troca papel ou ativa e desativa; a mudança corta as sessões abertas do usuário."""
    previous = UserRepository(session).get(user_id)
    before = {"role": previous.role, "is_active": previous.is_active} if previous else None
    try:
        user, sessions_cutoff = UserService(UserRepository(session)).update(
            user_id, role=body.role, is_active=body.is_active
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    note(request, before=before, after={"role": user.role, "is_active": user.is_active})
    _cut(request, user, sessions_cutoff)
    logger.info(
        "usuário alterado",
        extra={
            "user_id": str(user.id),
            "role": user.role,
            "is_active": user.is_active,
            "by": _actor(request),
        },
    )
    return to_response(user)


@router.post("/{user_id}/password", response_model=UserResponse)
def reset_password(
    user_id: UUID, body: ResetPasswordInput, session: SessionDep, request: Request
) -> UserResponse:
    """Owner define senha nova para o usuário e corta as sessões abertas dele."""
    try:
        user, sessions_cutoff = UserService(UserRepository(session)).reset_password(
            user_id, body.password
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    _cut(request, user, sessions_cutoff)
    logger.info("senha redefinida", extra={"user_id": str(user.id), "by": _actor(request)})
    return to_response(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: UUID, session: SessionDep, request: Request) -> Response:
    """Remove o usuário; o serviço recusa apagar a si mesmo e o último owner."""
    try:
        UserService(UserRepository(session)).delete(user_id, actor_id=_actor(request))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    logger.info("usuário removido", extra={"user_id": str(user_id), "by": _actor(request)})
    return Response(status_code=204)
