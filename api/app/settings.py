from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    jwt_private_key: str
    jwt_public_key: str
    # Chave pública da troca anterior: tokens assinados com ela continuam valendo até vencer
    # (ADR-0026). A emissão usa sempre a atual
    jwt_previous_public_key: str | None = None
    log_level: str = "INFO"
    # "development" liga /docs, /redoc e /openapi.json; qualquer outro valor os desliga
    app_env: str = "production"
    redis_url: str | None = None
    # pool do SQLAlchemy por processo; multiplique pelas réplicas e compare com o
    # max_connections do Postgres
    db_pool_size: int = 10
    db_max_overflow: int = 20
    # ingestão no worker separado (ADR-0039): a API só grava o job em ingest_job
    ingest_worker: bool = False
    # IPs ou CIDRs de proxies cujo X-Forwarded-For é confiável (separados por vírgula).
    # Vazio: o header é ignorado e vale o IP da conexão.
    trusted_proxies: str = ""
    # Chave Fernet que cifra os segredos em repouso: MCP, webhooks, alertas e conectores (ADR-0010)
    mcp_secrets_key: str | None = None
    # Chave Fernet anterior, só decifra durante a rotação (ADR-0026)
    mcp_secrets_previous_key: str | None = None
    # Hosts liberados da checagem de rede interna (separados por vírgula)
    mcp_allowed_hosts: str = ""
    # URL pública da API, usada para montar o endereço do /mcp nas integrações
    public_base_url: str | None = None
    # prazo da resposta ao titular (LGPD, art. 19, II); o aviso sai 2 dias antes (ADR-0036)
    data_subject_deadline_days: int = 15
    # trilha de auditoria (ADR-0041)
    audit_retention_days: int = 365
    # login por SSO (ADR-0042); sem issuer, client_id e redirect, o botão não aparece
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""
    oidc_label: str = "SSO"
    oidc_scopes: str = "openid email profile"
    oidc_role_claim: str = ""
    oidc_role_map: str = ""
    oidc_default_role: str = ""
    oidc_allowed_domains: str = ""
    # false: só o owner entra por senha (emergência); o resto, pelo SSO
    password_login: bool = True
    # Spans de agente, time, modelo e tool gravados no banco (árvore de execução)
    tracing_enabled: bool = True
    # traces por OTLP (ADR-0043); endpoint e cabeçalhos pelas variáveis OTEL_EXPORTER_OTLP_*
    otel_export_enabled: bool = False
    # true manda o texto da conversa e o id do usuário final ao fornecedor
    otel_export_content: bool = False
    otel_service_name: str = "automata-api"
    # Laço que roda as suítes agendadas (ADR-0016); no modo demo fica desligado de qualquer jeito
    eval_scheduler_enabled: bool = True
    # runs com background=true na fila durável do Agno, no Postgres (ADR-0020);
    # false volta às tasks em memória
    background_queue_durable: bool = True
    # sobrescreve o preço de referência por modelo, em JSON (ADR-0021)
    model_prices: str = ""
    # Bases de conhecimento (ADR-0012): embedder escolhido na criação de cada base
    knowledge_default_embedder: Literal["voyage", "openai"] = "voyage"
    # Lida pelo SDK da Voyage; a do OpenAI vem de OPENAI_API_KEY, como nos modelos
    voyage_api_key: str | None = None
    knowledge_max_upload_mb: int = 20
    knowledge_allowed_extensions: str = "pdf,docx,md,txt,csv,json"

    @property
    def knowledge_extensions(self) -> frozenset[str]:
        return frozenset(
            e.strip().lower().lstrip(".")
            for e in self.knowledge_allowed_extensions.split(",")
            if e.strip()
        )

    @property
    def docs_enabled(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
