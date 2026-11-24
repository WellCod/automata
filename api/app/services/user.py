import hashlib
import secrets
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select, update

from app.models.user import PasswordReset, User, UserRole
from app.repositories.user import UserRepository

# hasher argon2 do módulo; o nome curto fica porque o teste de enumeração o troca por monkeypatch
_ph = PasswordHasher()

# link de recuperação por e-mail (ADR-0045)
RESET_TTL = timedelta(minutes=30)


def _token_hash(token: str) -> str:
    """O banco guarda só o hash do token de recuperação: vazamento da tabela não dá o link."""
    return hashlib.sha256(token.encode()).hexdigest()


class ConflictError(ValueError):
    """Ação que deixaria a instância inconsistente; o router responde 409."""


# Login com e-mail inexistente verifica contra este hash para gastar o mesmo
# tempo de argon2 e não revelar pela latência quais contas existem
_DUMMY_HASH = _ph.hash("automata-dummy-password")


class UserService:
    """Contas do painel: criação, papel, senha, recuperação, login por senha e por SSO."""

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    def create_user(
        self, email: str, password: str, role: UserRole, *, must_change: bool = False
    ) -> User:
        """`must_change` na conta criada pelo owner: a senha que ele escolheu é provisória."""
        if self._repo.get_by_email(email) is not None:
            raise ValueError("Email já cadastrado")
        self._check_seats()
        user = self._repo.create(email=email, hashed_password=_ph.hash(password), role=role)
        user.must_change_password = must_change
        return user

    def _check_seats(self) -> None:
        """Recusa conta nova acima do limite de usuários do plano."""
        from app.settings import get_settings

        limit = get_settings().plan_max_users
        if limit and self._repo.count() >= limit:
            # limite do plano contratado (COM-06)
            raise ValueError(f"o plano permite {limit} usuários")

    def _get(self, user_id: UUID) -> User:
        user = self._repo.get(user_id)
        if user is None:
            raise LookupError("Usuário não encontrado")
        return user

    def _keeps_an_owner(self, user: User, *, role: UserRole, active: bool) -> None:
        """Recusa a mudança que tiraria o último owner ativo da instância."""
        is_active_owner = user.role == UserRole.owner and user.is_active
        stays_active_owner = role == UserRole.owner and active
        if is_active_owner and not stays_active_owner and self._repo.count_active_owners() <= 1:
            raise ConflictError("A instância precisa de ao menos um owner ativo")

    def _cut_sessions(self, user: User) -> datetime:
        """Invalida os tokens emitidos até agora: o JWT anterior ao corte é recusado."""
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
        session_cutoff = self._cut_sessions(user)
        self._repo._session.flush()
        return user, session_cutoff

    def reset_password(self, user_id: UUID, password: str) -> tuple[User, datetime]:
        """Senha definida pelo owner: provisória, a pessoa troca no próximo login."""
        user = self._get(user_id)
        user.hashed_password = _ph.hash(password)
        user.must_change_password = True
        session_cutoff = self._cut_sessions(user)
        self._repo._session.flush()
        return user, session_cutoff

    def change_own_password(self, user_id: UUID, current: str, new: str) -> tuple[User, datetime]:
        """Troca pela própria pessoa, com a senha atual. Corta as outras sessões."""
        user = self._get(user_id)
        if not user.hashed_password:
            raise ConflictError("Conta do SSO: a senha é a do provedor")
        try:
            _ph.verify(user.hashed_password, current)
        except VerifyMismatchError as exc:
            raise ValueError("Senha atual incorreta") from exc
        if current == new:
            raise ValueError("A nova senha precisa ser diferente da atual")
        return user, self._set_password(user, new)

    def _set_password(self, user: User, password: str) -> datetime:
        """Senha escolhida pela própria pessoa: deixa de ser provisória e corta as sessões."""
        user.hashed_password = _ph.hash(password)
        user.must_change_password = False
        session_cutoff = self._cut_sessions(user)
        self._repo._session.flush()
        return session_cutoff

    def request_reset(self, email: str, now: datetime) -> tuple[User, str] | None:
        """Token de recuperação para conta ativa com senha; None para qualquer outra."""
        user = self._repo.get_by_email(email)
        if user is None or not user.is_active or not user.hashed_password:
            return None
        session = self._repo._session
        # um link válido por vez: o novo derruba os anteriores
        session.execute(
            update(PasswordReset)
            .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
            .values(used_at=now)
        )
        token = secrets.token_urlsafe(32)
        session.add(
            PasswordReset(
                user_id=user.id, token_hash=_token_hash(token), expires_at=now + RESET_TTL
            )
        )
        session.flush()
        return user, token

    def reset_with_token(self, token: str, password: str, now: datetime) -> tuple[User, datetime]:
        """Troca a senha pelo link de recuperação, que vale uma vez só."""
        session = self._repo._session
        # trava a linha: dois envios do mesmo link ao mesmo tempo não usam o token duas vezes
        reset = session.scalar(
            select(PasswordReset)
            .where(PasswordReset.token_hash == _token_hash(token))
            .with_for_update()
        )
        if reset is None or reset.used_at is not None or reset.expires_at <= now:
            raise ValueError("Link inválido ou vencido. Peça outro.")
        user = self._get(reset.user_id)
        if not user.is_active:
            # mesma mensagem do link vencido: não revela que a conta foi desativada
            raise ValueError("Link inválido ou vencido. Peça outro.")
        reset.used_at = now
        return user, self._set_password(user, password)

    def delete(self, user_id: UUID, *, actor_id: str | None) -> None:
        """Remove conta já desativada; ninguém remove a própria."""
        user = self._get(user_id)
        if actor_id is not None and str(user.id) == actor_id:
            raise ConflictError("Você não pode remover a própria conta")
        if user.is_active:
            # desativar antes corta as sessões; remoção direta deixaria o token valendo
            raise ConflictError("Desative o usuário antes de remover")
        self._repo.delete(user)

    def authenticate(self, email: str, password: str) -> User:
        """Login por senha; toda recusa custa o mesmo argon2 e dá a mesma mensagem."""
        user = self._repo.get_by_email(email)
        if user is None or not user.is_active:
            with suppress(VerifyMismatchError):
                _ph.verify(_DUMMY_HASH, password)
            raise ValueError("Credenciais inválidas")
        if not user.hashed_password:
            # conta do SSO: sem senha, mesmo custo e mesma resposta de credencial errada
            with suppress(VerifyMismatchError):
                _ph.verify(_DUMMY_HASH, password)
            raise ValueError("Credenciais inválidas")
        try:
            _ph.verify(user.hashed_password, password)
        except VerifyMismatchError as exc:
            raise ValueError("Credenciais inválidas") from exc
        user.last_login_at = datetime.now(UTC)
        # parâmetros do argon2 mudaram desde o hash: regrava com a senha que acabou de chegar
        if _ph.check_needs_rehash(user.hashed_password):
            user.hashed_password = _ph.hash(password)
            self._repo._session.flush()
        return user

    def sso_login(
        self,
        *,
        issuer: str,
        subject: str,
        email: str | None,
        email_verified: bool,
        role: UserRole,
    ) -> tuple[User, datetime | None]:
        """Conta do login por SSO (ADR-0042). Devolve o corte de sessão quando o papel mudou."""
        session = self._repo._session
        user = session.scalars(
            select(User).where(User.sso_issuer == issuer, User.sso_subject == subject)
        ).first()
        if user is None:
            if not email:
                raise PermissionError("O provedor não informou o e-mail")
            user = self._repo.get_by_email(email)
            if user is not None:
                # ligar por e-mail só com e-mail confirmado pelo provedor: senão qualquer
                # conta do provedor com o e-mail do owner tomaria a conta dele
                if not email_verified:
                    raise PermissionError("E-mail não verificado no provedor")
                if user.sso_subject is not None:
                    raise PermissionError("Conta já ligada a outro login do provedor")
            else:
                # conta nova só com e-mail confirmado: senão o e-mail de outra pessoa fica
                # ocupado por quem se cadastrou no provedor com ele (Fase 49)
                if not email_verified:
                    raise PermissionError("E-mail não verificado no provedor")
                try:
                    self._check_seats()
                except ValueError as exc:
                    # o login por SSO responde 403 com o motivo
                    raise PermissionError(str(exc)) from exc
                user = User(email=email, hashed_password=None, role=role)
                session.add(user)
            user.sso_issuer = issuer
            user.sso_subject = subject
            session.flush()
        if not user.is_active:
            raise PermissionError("Conta desativada")
        # o papel segue o grupo do provedor a cada login
        session_cutoff: datetime | None = None
        if user.role != role:
            try:
                user, session_cutoff = self.update(user.id, role=role, is_active=None)
            except ConflictError:
                # último owner ativo: entra com o papel atual
                session_cutoff = None
        user.last_login_at = datetime.now(UTC)
        session.flush()
        return user, session_cutoff
