from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.models.user import User, UserRole
from app.repositories.user import UserRepository

_ph = PasswordHasher()


class ConflictError(ValueError):
    pass


# Login com e-mail inexistente verifica contra este hash para gastar o mesmo
# tempo de argon2 e não revelar pela latência quais contas existem
_DUMMY_HASH = _ph.hash("automata-dummy-password")


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    def create_user(self, email: str, password: str, role: UserRole) -> User:
        if self._repo.get_by_email(email) is not None:
            raise ValueError("Email já cadastrado")
        return self._repo.create(email=email, hashed_password=_ph.hash(password), role=role)

    def _get(self, user_id: UUID) -> User:
        user = self._repo.get(user_id)
        if user is None:
            raise LookupError("Usuário não encontrado")
        return user

    def _keeps_an_owner(self, user: User, *, role: UserRole, active: bool) -> None:
        losing = user.role == UserRole.owner and user.is_active
        stays = role == UserRole.owner and active
        if losing and not stays and self._repo.count_active_owners() <= 1:
            raise ConflictError("A instância precisa de ao menos um owner ativo")

    def _cut_sessions(self, user: User) -> datetime:
        now = datetime.now(UTC)
        user.tokens_valid_after = now
        return now

    def update(
        self, user_id: UUID, *, role: UserRole | None, is_active: bool | None
    ) -> tuple[User, datetime | None]:
        """Muda papel e/ou estado. Devolve o corte de sessão quando houve mudança."""
        user = self._get(user_id)
        new_role = role if role is not None else user.role
        new_active = is_active if is_active is not None else user.is_active
        if new_role == user.role and new_active == user.is_active:
            return user, None
        self._keeps_an_owner(user, role=new_role, active=new_active)
        user.role = new_role
        user.is_active = new_active
        cut = self._cut_sessions(user)
        self._repo._session.flush()
        return user, cut

    def reset_password(self, user_id: UUID, password: str) -> tuple[User, datetime]:
        user = self._get(user_id)
        user.hashed_password = _ph.hash(password)
        cut = self._cut_sessions(user)
        self._repo._session.flush()
        return user, cut

    def delete(self, user_id: UUID, *, actor_id: str | None) -> None:
        user = self._get(user_id)
        if actor_id is not None and str(user.id) == actor_id:
            raise ConflictError("Você não pode remover a própria conta")
        if user.is_active:
            # desativar antes corta as sessões; remoção direta deixaria o token valendo
            raise ConflictError("Desative o usuário antes de remover")
        self._repo.delete(user)

    def authenticate(self, email: str, password: str) -> User:
        user = self._repo.get_by_email(email)
        if user is None or not user.is_active:
            with suppress(VerifyMismatchError):
                _ph.verify(_DUMMY_HASH, password)
            raise ValueError("Credenciais inválidas")
        try:
            _ph.verify(user.hashed_password, password)
        except VerifyMismatchError as e:
            raise ValueError("Credenciais inválidas") from e
        user.last_login_at = datetime.now(UTC)
        if _ph.check_needs_rehash(user.hashed_password):
            user.hashed_password = _ph.hash(password)
            self._repo._session.flush()
        return user
