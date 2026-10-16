"""Login com e-mail inexistente ou inativo também paga o custo do argon2."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from argon2 import PasswordHasher

from app.services import user as user_module
from app.services.user import UserService


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    ph = MagicMock(wraps=PasswordHasher())
    monkeypatch.setattr(user_module, "_ph", ph)
    return ph


def _service(found: object) -> UserService:
    repo = MagicMock()
    repo.get_by_email.return_value = found
    return UserService(repo)


def test_email_inexistente_roda_verify_contra_hash_fixo(spy: MagicMock) -> None:
    with pytest.raises(ValueError, match="Credenciais inválidas"):
        _service(None).authenticate("ninguem@x.com", "Senha123!")
    spy.verify.assert_called_once_with(user_module._DUMMY_HASH, "Senha123!")


def test_usuario_inativo_roda_verify_contra_hash_fixo(spy: MagicMock) -> None:
    inativo = SimpleNamespace(is_active=False, hashed_password="irrelevante")
    with pytest.raises(ValueError, match="Credenciais inválidas"):
        _service(inativo).authenticate("inativo@x.com", "Senha123!")
    spy.verify.assert_called_once_with(user_module._DUMMY_HASH, "Senha123!")


def test_usuario_existente_verifica_o_proprio_hash(spy: MagicMock) -> None:
    hashed = PasswordHasher().hash("Senha123!")
    ativo = SimpleNamespace(is_active=True, hashed_password=hashed)
    assert _service(ativo).authenticate("a@x.com", "Senha123!") is ativo
    spy.verify.assert_called_once_with(hashed, "Senha123!")
