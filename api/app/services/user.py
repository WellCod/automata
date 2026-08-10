from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.models.user import User, UserRole
from app.repositories.user import UserRepository

_ph = PasswordHasher()


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    def create_user(self, email: str, password: str, role: UserRole) -> User:
        if self._repo.get_by_email(email) is not None:
            raise ValueError("Email já cadastrado")
        return self._repo.create(
            email=email, hashed_password=_ph.hash(password), role=role
        )

    def authenticate(self, email: str, password: str) -> User:
        user = self._repo.get_by_email(email)
        if user is None or not user.is_active:
            raise ValueError("Credenciais inválidas")
        try:
            _ph.verify(user.hashed_password, password)
        except VerifyMismatchError as e:
            raise ValueError("Credenciais inválidas") from e
        if _ph.check_needs_rehash(user.hashed_password):
            user.hashed_password = _ph.hash(password)
            self._repo._session.flush()
        return user
