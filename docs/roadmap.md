# Roadmap — Fases 4 a 7

Plano de ação derivado de auditoria técnica e de segurança realizada em 2026-08-12.
Ordem otimizada: vulnerabilidades críticas primeiro, depois estabilidade, observabilidade e qualidade.

---

## Fase 4 — Segurança (PRs 41–44)

### PR 41 — `fix(security): remove jwt_private_key do container web`

**Problema:** `JWT_PRIVATE_KEY` está nas env vars do container web em `docker-compose.yml` e `docker-compose.demo.yml`. A chave privada deve existir **somente** na API — o painel só precisa assinar cookies via o BFF, que já usa `JWT_PRIVATE_KEY` do processo Node (env de build/runtime do Next.js), não do container Docker.

**Arquivos:**
- `docker-compose.yml` — remover `JWT_PRIVATE_KEY` do serviço `web`
- `docker-compose.demo.yml` — remover `JWT_PRIVATE_KEY` do serviço `web`
- `.env.example` — adicionar comentário explicando que web só precisa da chave em runtime Next.js (não no compose)

**O que fazer:**
1. Remover a linha `JWT_PRIVATE_KEY: ${JWT_PRIVATE_KEY}` do bloco `environment` do serviço `web` em ambos os compose files
2. Verificar que `JWT_PRIVATE_KEY` ainda está disponível para o processo Next.js via `.env.local` ou variável de ambiente do host (não via Docker environment — isso é diferente)
3. Atualizar `.env.example` com nota explicando a separação

**Critério de aceite:** `docker inspect automata-web` não mostra `JWT_PRIVATE_KEY` nas env vars do container.

---

### PR 42 — `fix(security): validação jwt no proxy bff e cookie secure`

**Problema 1:** `web/src/app/api/[...proxy]/route.ts` verifica apenas se o cookie existe, não se o JWT é válido. Token expirado ou adulterado passa pelo proxy.

**Problema 2:** Cookie `automata_token` sem flag `secure: true` — transmitido em texto claro sobre HTTP.

**Arquivos:**
- `web/src/app/api/[...proxy]/route.ts` — adicionar verificação de expiração do JWT antes de proxar
- `web/src/app/api/auth/login/route.ts` — adicionar `secure: process.env.NODE_ENV === "production"`
- `web/package.json` — adicionar dependência `jose` (já pode estar no projeto via agno; verificar)

**O que fazer (proxy):**
```typescript
// Decodificar o JWT sem verificar assinatura (a API faz isso)
// mas verificar expiração para evitar proxar tokens claramente expirados
import { decodeJwt } from "jose";

const token = req.cookies.get("automata_token")?.value;
if (!token) return new NextResponse("Não autorizado", { status: 401 });

try {
  const claims = decodeJwt(token);
  const now = Math.floor(Date.now() / 1000);
  if (claims.exp && claims.exp < now) {
    const res = new NextResponse("Sessão expirada", { status: 401 });
    res.cookies.delete("automata_token");
    return res;
  }
} catch {
  return new NextResponse("Token inválido", { status: 401 });
}
```

**O que fazer (cookie):**
```typescript
res.cookies.set("automata_token", data.access_token!, {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  path: "/",
  maxAge: 60 * 60,
});
```

**Critério de aceite:** Token com `exp` no passado retorna 401 no proxy sem passar para a API.

---

### PR 43 — `fix(security): headers de segurança http`

**Problema:** API e painel não retornam headers de segurança. Sem `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security` e `Content-Security-Policy`.

**Arquivos:**
- `api/app/main.py` — adicionar middleware de headers de segurança
- `web/next.config.ts` — adicionar bloco `headers`

**O que fazer (API):**
```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

# Em create_app(), antes do mount:
base.add_middleware(SecurityHeadersMiddleware)
```

**O que fazer (Next.js):**
```typescript
const nextConfig: NextConfig = {
  output: "standalone",
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-XSS-Protection", value: "1; mode=block" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ],
    }];
  },
};
```

**Critério de aceite:** `curl -I http://localhost:8000/health` e `curl -I http://localhost:3000` retornam os headers esperados.

---

### PR 44 — `fix(security): política de senha, csrf e ip forwarding`

**Problema 1:** Senha aceita apenas 8 caracteres sem complexidade — `api/app/schemas/user.py:22`.

**Problema 2:** Rate limiting usa `request.client.host` que é sempre o IP do proxy atrás de nginx/CloudFlare — `api/app/routers/auth.py:57`.

**Problema 3:** Route Handlers de mutação sem validação de origem.

**Arquivos:**
- `api/app/schemas/user.py` — aumentar min_length e adicionar validator de complexidade
- `api/app/routers/auth.py` — função `get_client_ip()` que lê `X-Forwarded-For`
- `web/src/middleware.ts` — validar `Origin` em requests de mutação

**O que fazer (senha):**
```python
@field_validator("password")
@classmethod
def validate_password_strength(cls, v: str) -> str:
    if len(v) < 12:
        raise ValueError("Senha deve ter ao menos 12 caracteres")
    if not any(c.isupper() for c in v):
        raise ValueError("Senha deve ter ao menos uma letra maiúscula")
    if not any(c.isdigit() for c in v):
        raise ValueError("Senha deve ter ao menos um número")
    return v
```

**O que fazer (IP):**
```python
def get_client_ip(request: Request) -> str:
    if forwarded := request.headers.get("X-Forwarded-For"):
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
```

**O que fazer (CSRF básico via middleware Next.js):**
```typescript
// web/src/middleware.ts — adicionar ao middleware existente
const SAFE_METHODS = ["GET", "HEAD", "OPTIONS"];
if (!SAFE_METHODS.includes(request.method)) {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (origin && host && !origin.endsWith(host)) {
    return new NextResponse("Forbidden", { status: 403 });
  }
}
```

**Critério de aceite:** Senha `"abcd1234"` rejeitada; `"Abcd1234!"` aceita. `curl -X POST -H "Origin: http://evil.com"` retorna 403.

---

## Fase 5 — Estabilidade e Performance (PRs 45–47)

### PR 45 — `fix(api): pool de conexões sqlalchemy compartilhado`

**Problema:** `create_engine(get_settings().database_url)` chamado em **cada request** nos routers `auth`, `configs`, `usage` — nova pool de conexões por requisição, overhead de ~100ms.

**Arquivos:**
- `api/app/db.py` — novo arquivo com engine singleton e `get_session()`
- `api/app/routers/auth.py` — substituir create_engine local
- `api/app/routers/configs.py` — substituir create_engine local
- `api/app/routers/usage.py` — substituir create_engine local
- `api/app/main.py` — inicializar engine no startup

**O que fazer:**
```python
# api/app/db.py (novo)
from contextlib import contextmanager
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

_engine = None

def init_engine(db_url: str) -> None:
    global _engine
    _engine = create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

@contextmanager
def get_session() -> Generator[Session, None, None]:
    assert _engine is not None, "Engine não inicializado"
    with Session(_engine) as session:
        yield session
```

```python
# api/app/main.py — no create_app()
from app.db import init_engine
init_engine(settings.database_url)
```

**Critério de aceite:** `docker stats` mostra conexões estáveis ao banco em carga; sem spike de novas conexões por request.

---

### PR 46 — `chore(infra): restart policies, resource limits e health check da api`

**Problema 1:** Containers sem `restart: on-failure` — caem e ficam offline sem intervenção.

**Problema 2:** Sem `deploy.resources.limits` — um processo buga e consome 100% CPU/RAM.

**Problema 3:** Health check do container `api` não existe (só existe para o `db`).

**Arquivos:**
- `docker-compose.yml` — adicionar restart e deploy.resources em api, db e web
- `docker-compose.demo.yml` — mesmas adições

**O que fazer:**
```yaml
services:
  db:
    restart: on-failure:5
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M

  api:
    restart: on-failure:3
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 30s

  web:
    restart: on-failure:3
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
```

**Critério de aceite:** `docker compose ps` mostra `healthy` para api após 30s. Processo que bate o limit é reiniciado automaticamente.

---

### PR 47 — `feat(api): índices de banco e cache http em capabilities`

**Problema 1:** Sem índices compostos em `agent_config_version(config_id, status)` e `usage_event(agent_config_id, period)` — queries lentas em escala.

**Problema 2:** `GET /api/v1/models/capabilities` recalcula a cada request; dados são estáticos em runtime.

**Arquivos:**
- `api/alembic/versions/XXXX_add_performance_indexes.py` — nova migration
- `api/app/routers/models.py` — adicionar `Cache-Control` na resposta

**O que fazer (migration):**
```python
def upgrade() -> None:
    op.create_index(
        "ix_agent_config_version_config_status",
        "agent_config_version",
        ["config_id", "status"],
    )
    op.create_index(
        "ix_usage_event_period_agent",
        "usage_event",
        ["agent_config_id", "period"],
    )
```

**O que fazer (cache):**
```python
@router.get("/capabilities")
def list_capabilities(response: Response) -> dict[str, dict[str, bool]]:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return {model_id: asdict(caps) for model_id, caps in all_capabilities().items()}
```

**Critério de aceite:** `EXPLAIN ANALYZE` nas queries de config e usage mostra Index Scan. `curl -I /api/v1/models/capabilities` retorna `Cache-Control: public, max-age=3600`.

---

## Fase 6 — Observabilidade (PRs 48–49)

### PR 48 — `feat(api): logging estruturado com request-id`

**Problema:** Nenhum logging nos routers de auth, configs e usage — impossível debugar falhas em produção.

**Arquivos:**
- `api/app/logging_config.py` — novo: JSONFormatter + setup
- `api/app/main.py` — middleware de request-id + setup do logging
- `api/app/routers/auth.py` — adicionar logs de login attempt, sucesso, falha
- `api/app/routers/configs.py` — logs de operações críticas (publicar, rollback)

**O que fazer:**
```python
# api/app/logging_config.py (novo)
import json, logging, uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
            **({"exc": self.formatException(record.exc_info)} if record.exc_info else {}),
        })

def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
```

```python
# main.py — middleware
@outer.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        request_id_var.reset(token)
```

**Critério de aceite:** `docker logs automata-api-1 | python3 -c "import json,sys; [json.loads(l) for l in sys.stdin]"` não levanta exceção (JSON válido linha a linha).

---

### PR 49 — `feat(api): health check com validação de banco`

**Problema:** Não existe endpoint `/health` próprio na API — o AgentOS tem um mas não valida conexão com Postgres. Docker considera container saudável mesmo com banco inacessível.

**Arquivos:**
- `api/app/routers/health.py` — novo router com `/health/live` e `/health/ready`
- `api/app/main.py` — registrar router
- `docker-compose.yml` — atualizar healthcheck da api para usar `/health/ready`
- `docker-compose.demo.yml` — idem

**O que fazer:**
```python
# api/app/routers/health.py (novo)
from fastapi import APIRouter
from sqlalchemy import text
from app.db import get_session

router = APIRouter(tags=["health"])

@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/health/ready")
def readiness() -> dict[str, str]:
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail="banco indisponível") from e
    return {"status": "ready"}
```

**Critério de aceite:** Com banco parado, `GET /health/ready` retorna 503 e `docker compose ps` mostra o container como `unhealthy`.

---

## Fase 7 — Qualidade e CI/CD (PRs 50–52)

### PR 50 — `chore(ci): testes de integração, coverage e cache de layers docker`

**Problema 1:** `pytest -m "not nightly"` pula testes de integração (testcontainers) no CI.

**Problema 2:** Sem coverage obrigatória — lacunas invisíveis.

**Problema 3:** CI constrói imagens Docker sem aproveitar cache do GitHub Actions.

**Arquivos:**
- `.github/workflows/ci.yml` — ativar testcontainers, adicionar coverage, adicionar cache buildx
- `api/pyproject.toml` — adicionar `pytest-cov` e `addopts` com `--cov`

**O que fazer (pyproject.toml):**
```toml
[dependency-groups]
dev = [
    "pytest-cov>=6.0",
    ...
]

[tool.pytest.ini_options]
addopts = "--cov=app --cov-report=term-missing --cov-fail-under=70"
```

**O que fazer (ci.yml — job api):**
```yaml
- run: uv run pytest -m "not nightly"
  working-directory: api
  env:
    TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE: /var/run/docker.sock

# No job de build Docker:
- uses: docker/build-push-action@v6
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

**Critério de aceite:** CI roda testes de integração sem falhar; falha se coverage < 70%; segundo build do mesmo PR é 40–60% mais rápido.

---

### PR 51 — `feat(infra): redis e rate limiting distribuído`

**Problema:** Rate limiting em `_login_attempts` dict em memória — não funciona com mais de uma instância da API e vaza memória ao longo do tempo.

**Arquivos:**
- `docker-compose.yml` — adicionar serviço `redis`
- `docker-compose.demo.yml` — idem
- `api/app/routers/auth.py` — substituir dict por Redis
- `api/pyproject.toml` — adicionar `redis>=5.0`
- `.env.example` — adicionar `REDIS_URL`
- `api/app/settings.py` — adicionar `redis_url`

**O que fazer:**
```python
# api/app/routers/auth.py
import redis as redis_lib
from app.settings import get_settings

def _get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(get_settings().redis_url, decode_responses=True)

def _check_rate_limit(ip: str) -> None:
    r = _get_redis()
    key = f"rl:login:{ip}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, _RATE_WINDOW)
    if count > _RATE_LIMIT:
        raise HTTPException(
            status_code=429, detail="Muitas tentativas. Tente novamente em breve."
        )
```

```yaml
# docker-compose.yml
redis:
  image: redis:7-alpine
  restart: on-failure:5
  deploy:
    resources:
      limits:
        cpus: "0.5"
        memory: 128M
```

**Critério de aceite:** Com duas instâncias da API, 5 tentativas de login distribuídas entre elas resultam em 429 na 6ª tentativa.

---

### PR 52 — `chore(dev): script de bootstrap e env de desenvolvimento`

**Problema:** Dev novo precisa gerar chaves RSA manualmente, preencher `.env` sem orientação, e não tem valores padrão para seed.

**Arquivos:**
- `scripts/setup-dev.py` — novo: gera chaves RSA, cria `.env`, verifica pré-requisitos
- `.env.example` — enriquecer com comentários e valores padrão não sensíveis
- `justfile` — adicionar target `setup`
- `README.md` — atualizar "Rodando local" para usar o script

**O que fazer:**
```python
# scripts/setup-dev.py (novo)
"""Bootstrap do ambiente de desenvolvimento."""
import shutil, subprocess, sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def check_prereqs():
    for cmd in ["docker", "python3", "node", "pnpm"]:
        if not shutil.which(cmd):
            print(f"[ERRO] {cmd} não encontrado")
            sys.exit(1)

def generate_keys() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private, public

def setup():
    check_prereqs()
    env_path = Path(".env")
    if env_path.exists():
        print("[OK] .env já existe, pulando geração de chaves")
        return
    private, public = generate_keys()
    example = Path(".env.example").read_text()
    env = (
        example
        .replace("<GERAR_COM_setup-dev.py>", private.replace("\n", "\\n"))
        .replace("<EXTRAIR_DA_CHAVE_PRIVADA>", public.replace("\n", "\\n"))
        .replace("<ESCOLHER_SENHA_SEGURA>", "dev-automata-2024")
    )
    env_path.write_text(env)
    print("[OK] .env criado com chaves RSA geradas")

if __name__ == "__main__":
    setup()
```

**Critério de aceite:** `python3 scripts/setup-dev.py && docker compose -f docker-compose.yml -f docker-compose.dev.yml up` funciona sem intervenção manual em máquina limpa.

---

## Resumo por fase

| Fase | PRs | Foco | Pré-requisito |
|------|-----|------|---------------|
| 4 — Segurança | 41–44 | Chave privada, JWT, headers, senha | — |
| 5 — Estabilidade | 45–47 | Pool DB, restart, índices, cache | PR 45 antes de 46 |
| 6 — Observabilidade | 48–49 | Logging, health check | PR 45 (pool) |
| 7 — Qualidade | 50–52 | CI, Redis, bootstrap | PR 46 (Redis infra) |
| 8 — Agentes Vivos | 54–58 | Factories dinâmicas, runs, métricas, MCP | — |

---

## Fase 8 — Agentes Vivos (PRs 54–58)

Fecha o gap estrutural — `main.py` tinha `factories = []`, nenhum agente era carregado do banco. Adiciona visibilidade de execução e resolve pendências do ADR-0009.

---

### PR 54 — `feat(api): carregamento dinâmico de factories a partir de configs publicados`

**Problema:** `create_app()` inicializava `factories = []` — configs publicados existem no banco mas nenhum agente estava registrado no AgentOS.

**Arquivos:**
- `api/app/main.py` — função `_load_published_factories(db)` que consulta configs com `current_version_id IS NOT NULL` e cria um `AgentFactory` por config; erro no carregamento loga warning e continua com lista vazia

**Critério de aceite:** Após publicar um config, o endpoint `/agents/{id}` responde sem redeploy manual das factories.

---

### PR 55 — `feat(api): router de runs — histórico e status por agente`

**Problema:** Não há registro de execuções — impossível saber se um agente está falhando, lento ou sequer sendo invocado.

**Arquivos:**
- `api/alembic/versions/0006_create_agent_run.py` — nova tabela `agent_run(id, agent_config_id, user_id, run_id, status, duration_ms, error, created_at)`
- `api/app/models/run.py` — model SQLAlchemy
- `api/app/repositories/run.py` — `RunRepository` com `record` e `list_by_config`
- `api/app/agents/factory.py` — adicionar `post_hook` que persiste o run com status e duração
- `api/app/routers/runs.py` — `GET /api/v1/configs/{id}/runs`

**Critério de aceite:** Após invocar um agente, `GET /api/v1/configs/{id}/runs` retorna o run com status e duração.

---

### PR 56 — `feat(web): painel de runs em tempo real com SSE`

**Problema:** Não há UI para inspecionar execuções — operador não sabe o estado do agente sem acessar logs do container.

**Arquivos:**
- `web/src/components/runs-panel.tsx` — tabela de runs com status, duração e erro
- `web/src/app/api/configs/[id]/runs/route.ts` — BFF proxy para `GET /api/v1/configs/{id}/runs`
- `web/src/app/(dashboard)/configs/[id]/page.tsx` — aba "Runs" no painel do config

**Critério de aceite:** Painel atualiza a lista de runs a cada 5s via polling (SSE pode ser fase seguinte).

---

### PR 57 — `feat(api): métricas por agente — p50/p95 de latência e taxa de erro`

**Problema:** Sem percentis de latência, impossível detectar degradação de performance por versão de config.

**Arquivos:**
- `api/app/routers/runs.py` — endpoint `GET /api/v1/configs/{id}/metrics?period=30d` com `percentile_cont` via PostgreSQL
- `web/src/components/metrics-panel.tsx` — cards p50/p95/taxa de erro

**Critério de aceite:** `GET /api/v1/configs/{id}/metrics` retorna `{p50_ms, p95_ms, error_rate, total_runs}`.

---

### PR 58 — `fix(api): reconexão de MCPTools e validação de escopo em /mcp`

**Problema:** ADR-0009 tem dois itens abertos: (1) reconexão automática de MCPTools quando conexão cai; (2) `/mcp` não valida JWT/scopes da mesma forma que as rotas do AgentOS.

**Arquivos:**
- `api/app/main.py` — habilitar `enable_mcp_server=True` com configuração de auth
- Verificar e documentar comportamento de reconexão do Agno

**Critério de aceite:** `curl /mcp` sem token retorna 401. Conexão MCP reconecta após queda de rede (teste manual).
