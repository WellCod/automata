from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    jwt_private_key: str
    jwt_public_key: str
    log_level: str = "INFO"
    # "development" liga /docs, /redoc e /openapi.json; qualquer outro valor os desliga
    app_env: str = "production"
    redis_url: str | None = None
    # IPs ou CIDRs de proxies cujo X-Forwarded-For é confiável (separados por vírgula).
    # Vazio: o header é ignorado e vale o IP da conexão.
    trusted_proxies: str = ""
    # Chave Fernet que cifra headers de servidores MCP (ADR-0010)
    mcp_secrets_key: str | None = None
    # Hosts liberados da checagem de rede interna (separados por vírgula)
    mcp_allowed_hosts: str = ""
    # URL pública da API, usada para montar o endereço do /mcp nas integrações
    public_base_url: str | None = None
    # Spans de agente, time, modelo e tool gravados no banco (árvore de execução)
    tracing_enabled: bool = True

    @property
    def docs_enabled(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
