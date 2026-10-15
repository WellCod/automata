from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    jwt_private_key: str
    jwt_public_key: str
    log_level: str = "INFO"
    redis_url: str | None = None
    # IPs ou CIDRs de proxies cujo X-Forwarded-For é confiável (separados por vírgula).
    # Vazio: o header é ignorado e vale o IP da conexão.
    trusted_proxies: str = ""
    # Chave Fernet que cifra headers de servidores MCP (ADR-0010)
    mcp_secrets_key: str | None = None
    # Hosts liberados da checagem de rede interna (separados por vírgula)
    mcp_allowed_hosts: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
