"""Cifra de segredos em repouso: headers MCP, webhooks, destinos de alerta e conectores.

A chave atual cifra; a anterior (`MCP_SECRETS_PREVIOUS_KEY`) só decifra, durante a
rotação, até `python -m app.rotate_secrets` recifrar tudo (ADR-0010, ADR-0026).
"""

import json

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.settings import get_settings


class SecretsKeyMissing(RuntimeError):
    pass


def _current() -> Fernet:
    key = get_settings().mcp_secrets_key
    if not key:
        raise SecretsKeyMissing("MCP_SECRETS_KEY não configurada")
    return Fernet(key.encode())


def _fernet() -> MultiFernet:
    keys = [_current()]
    previous = get_settings().mcp_secrets_previous_key
    if previous:
        keys.append(Fernet(previous.encode()))
    return MultiFernet(keys)


def encrypt_json(data: dict[str, str]) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_json(token: str) -> dict[str, str]:
    try:
        raw = _fernet().decrypt(token.encode())
    except InvalidToken as exc:
        raise SecretsKeyMissing("MCP_SECRETS_KEY não decifra os segredos salvos") from exc
    result: dict[str, str] = json.loads(raw)
    return result


def on_current_key(token: str) -> bool:
    try:
        _current().decrypt(token.encode())
    except InvalidToken:
        return False
    return True


def reencrypt(token: str) -> str:
    """Recifra com a chave atual; levanta `SecretsKeyMissing` se nenhuma chave abrir."""
    try:
        return _fernet().rotate(token.encode()).decode()
    except InvalidToken as exc:
        raise SecretsKeyMissing("nenhuma chave configurada decifra o segredo") from exc
