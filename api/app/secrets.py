"""Cifra de segredos em repouso (headers de servidores MCP, ADR-0010)."""

import json

from cryptography.fernet import Fernet, InvalidToken

from app.settings import get_settings


class SecretsKeyMissing(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = get_settings().mcp_secrets_key
    if not key:
        raise SecretsKeyMissing("MCP_SECRETS_KEY não configurada")
    return Fernet(key.encode())


def encrypt_json(data: dict[str, str]) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_json(token: str) -> dict[str, str]:
    try:
        raw = _fernet().decrypt(token.encode())
    except InvalidToken as exc:
        raise SecretsKeyMissing("MCP_SECRETS_KEY não decifra os segredos salvos") from exc
    result: dict[str, str] = json.loads(raw)
    return result
