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
    user_id = getattr(request.state, "user_id", None)
    return str(user_id) if user_id else None


def _cut(request: Request, user: User, at: datetime | None) -> None:
    # vale já neste processo; os outros workers pegam no próximo refresh (30 s)
    revoked = getattr(request.app.state, "revoked_tokens", None)
    if at is not None and revoked is not None:
        revoked.cut_now(str(user.id), at.timestamp())


@me_router.get("", response_model=MeResponse)
def me(request: Request, session: SessionDep) -> MeResponse:
    """Quem está logado. Token de integração não tem usuário: volta só o sub."""
    sub = _actor(request) or ""
    try:
        user = UserRepository(session).get(UUID(sub))
    except ValueError:
        user = None
    if user is None:
        return MeResponse(id=sub, email=None, role=None)
    return MeResponse(id=str(user.id), email=user.email, role=user.role)


@me_router.post("/password", response_model=TokenResponse)
def change_own_password(
    body: ChangePasswordInput, session: SessionDep, request: Request
) -> TokenResponse:
    """Troca pela própria pessoa. Corta as outras sessões e devolve o token novo."""
    sub = _actor(request) or ""
    try:
        user_id = UUID(sub)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Só usuário do painel troca senha") from exc
    request.app.state.rate_limiter.check(f"password-change:{sub}", limit=5)
    try:
        user, cut = UserService(UserRepository(session)).change_own_password(
            user_id, body.current_password, body.new_password
        )
    except LookupError as exc:
        raise HTTPException(status_code=403, detail="Só usuário do painel troca senha") from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # o corte vale até o fim do segundo; o token novo sai no mesmo segundo
    cut = cut.replace(microsecond=0)
    user.tokens_valid_after = cut
    role = user.role
    session.commit()
    _cut(request, user, cut)
    logger.info("senha trocada pelo usuário", extra={"user_id": sub})
    return TokenResponse(access_token=issue_token(sub, ROLE_SCOPES[role]))


@router.get("", response_model=list[UserResponse])
def list_users(session: SessionDep) -> list[UserResponse]:
    return [to_response(u) for u in UserRepository(session).list_all()]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(body: CreateUserInput, session: SessionDep, request: Request) -> UserResponse:
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
    previous = UserRepository(session).get(user_id)
    before = {"role": previous.role, "is_active": previous.is_active} if previous else None
    try:
        user, cut = UserService(UserRepository(session)).update(
            user_id, role=body.role, is_active=body.is_active
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    note(request, before=before, after={"role": user.role, "is_active": user.is_active})
    _cut(request, user, cut)
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
    try:
        user, cut = UserService(UserRepository(session)).reset_password(user_id, body.password)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    _cut(request, user, cut)
    logger.info("senha redefinida", extra={"user_id": str(user.id), "by": _actor(request)})
    return to_response(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: UUID, session: SessionDep, request: Request) -> Response:
    try:
        UserService(UserRepository(session)).delete(user_id, actor_id=_actor(request))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    logger.info("usuário removido", extra={"user_id": str(user_id), "by": _actor(request)})
    return Response(status_code=204)
