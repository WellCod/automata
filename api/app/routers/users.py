"""Gestão de usuários da instância (só owner) e o usuário logado (/me)."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import (
    CreateUserInput,
    MeResponse,
    ResetPasswordInput,
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


@router.get("", response_model=list[UserResponse])
def list_users(session: SessionDep) -> list[UserResponse]:
    return [to_response(u) for u in UserRepository(session).list_all()]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(body: CreateUserInput, session: SessionDep, request: Request) -> UserResponse:
    try:
        user = UserService(UserRepository(session)).create_user(
            email=body.email, password=body.password, role=body.role
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
    try:
        user, cut = UserService(UserRepository(session)).update(
            user_id, role=body.role, is_active=body.is_active
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
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
