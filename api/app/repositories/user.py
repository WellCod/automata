from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))

    def create(self, email: str, hashed_password: str, role: UserRole) -> User:
        user = User(email=email, hashed_password=hashed_password, role=role)
        self._session.add(user)
        self._session.flush()
        return user

    def count(self) -> int:
        result = self._session.scalar(select(func.count()).select_from(User))
        return int(result) if result is not None else 0
