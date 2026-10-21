# Roadmap — Fases 4 a 16

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
| 11 — Auditoria 2026-10-15 | #66, #67, #79–#84 | Fecha a Fase 4, runtime de agentes, infra, UI/UX, revogação por `jti` | — |
| 12 — Multi-agente e MCP | #68–#78 | Servidores MCP, confirmação humana, times, integrações, árvore de execução | #67 |
| 13 — RAG | #85–#94 | Bases de conhecimento com pgvector e citações | Fase 12 |
| 14 — Guardrails | #95–#103 | Dados pessoais, injeção de prompt e bloqueios por agente | — |
| Usuários e redesign | #97, #100 | Gestão de usuários, tema claro e escuro | — |
| 15 — Workflows | #108–#114 | Etapas em sequência, paralelo, condição e loop sobre agentes e times | Fases 12 e 14 |
| 16 — Evals no painel | #118–#125 | Casos de teste por agente e time, juiz por LLM, regressão entre versões e gate de publicação | Fases 13 e 14 |
| 17 — Evals contínuos | #127 em diante | Suíte disparada por token de integração, agendamento e casos a partir de conversas reais | Fase 16 |

Fases 4 a 15 estão na `main` (estado em 2026-10-20); a 16 está em andamento.

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

---

## Fase 9 — Analytics (pós-Fase 8)

Painel analítico consolidado aproveitando `agent_run` e `usage_event` já persistidos.

### PRs entregues

- [x] PR 59 — `feat(web): painel analytics global — runs, latência, custo e tokens`
  - `RunRepository.metrics_global()` e `UsageRepository.usage_summary()` com dados cross-agente
  - `GET /api/v1/metrics/summary` e `GET /api/v1/metrics/by-agent` com filtro `period=Xd`
  - Página `/analytics` com 6 cards (conversas, falhas, p50, p95, tokens, custo) + tabela por agente
  - Link Analytics no sidebar

- [x] PR 60 — `fix(analytics): filtro de período na tabela de uso por agente`
  - Tabela "uso por agente" agora respeita o filtro 7d/30d/90d selecionado
  - Labels dos cards reescritos em linguagem acessível (sem "p50 latência")

- [x] PR 61 — `feat(analytics): seletor de intervalo de datas personalizado`
  - Parâmetros opcionais `start` e `end` (YYYY-MM-DD) nos dois endpoints de métricas
  - Repositórios refatorados para `since`/`until` ao invés de `period_days` fixo
  - Campos de data no painel ao lado dos botões de período pré-definido

---

## Fase 10 — Demo e Portfólio

Torna a plataforma demonstrável sem credencial de LLM e com dados realistas visíveis.

### Contexto

Para uso como portfólio, a plataforma precisa funcionar sem `ANTHROPIC_API_KEY` nem `OPENAI_API_KEY`. O mecanismo de replay (`DEMO_REPLAY=true`) já existia em `api/app/agents/models_map.py`, mas faltavam fixtures realistas e seed de dados.

### PR entregue — `chore/demo-seed-e-docs`

**Fixtures de resposta** (`api/fixtures/`):

| Arquivo | Usado por |
|---------|-----------|
| `claude-opus-4-7.json` | Analista Financeiro — análises de balanço, valuation, DCF, KPIs |
| `claude-sonnet-4-6.json` | Redator de Conteúdo, Assistente de Código — posts, scripts, code review |
| `claude-haiku-4-5.json` | Atendimento ao Cliente, Suporte Técnico — respostas curtas e objetivas |
| `default.json` | Fallback para qualquer modelo não listado |

Cada arquivo tem 10 respostas realistas em PT-BR. O `ReplayModel` cicla pela lista de forma determinística.

**Seed completo** (`uv run python scripts/seed.py full`):

Cria em sequência:
1. Usuário owner via `seed_minimal`
2. 5 agentes com instruções completas e versão publicada via `seed_demo`:
   - Analista Financeiro (`claude-opus-4-7`)
   - Redator de Conteúdo (`claude-sonnet-4-6`)
   - Atendimento ao Cliente (`claude-haiku-4-5`)
   - Suporte Técnico (`claude-haiku-4-5`)
   - Assistente de Código (`claude-sonnet-4-6`)
3. 500 runs históricos distribuídos nos últimos 90 dias via `seed_analytics`:
   - Taxas de erro por agente: 3–8%
   - Latências proporcionais ao modelo: haiku ~1,1s · sonnet ~2,8–3,5s · opus ~4,2s
   - Tokens e custo por run proporcional ao preço do modelo
   - Pesos de distribuição: atendimento (4×) > suporte (3×) > demais (2×)

**Documentação:**
- `DEMO.md` — guia completo de como rodar a demo local
- `README.md` — seção Demo reescrita com comandos prontos
- `docs/roadmap.md` — este documento

**Como rodar:**

```bash
DEMO_REPLAY=true docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
# Defina a senha do owner — ela não fica escrita em lugar nenhum
read -rsp "Senha do owner: " SEED_OWNER_PASSWORD; echo

docker exec \
  -e SEED_OWNER_EMAIL="admin@exemplo.com" \
  -e SEED_OWNER_PASSWORD="$SEED_OWNER_PASSWORD" \
  automata-api-1 uv run python scripts/seed.py full
```

**Critério de aceite:** Painel funcional com 5 agentes listados, modo teste respondendo via fixture, painel Analytics mostrando dados dos últimos 90 dias — sem nenhuma credencial de LLM configurada.

---

## Fase 11 — Auditoria 2026-10-15

Revisão de estrutura, segurança e UI/UX feita sobre a `main` em `cf186bc`. Os achados abaixo foram conferidos no código. A partir daqui o número do PR é o do GitHub, para não colidir com a numeração interna das fases anteriores.

### Ação manual pendente (fora do código)

O repositório é público e o histórico guarda duas senhas de owner antigas (README, DEMO, roadmap e `deploy.sh`, removidas no #64) e um par RSA de teste em `web/playwright.config.ts` (`9e52842`). O `deploy.sh` também enviava a chave privada JWT ao Vercel.

- [ ] Gerar par JWT novo em todo ambiente que rodou `scripts/deploy.sh` (apagar `.deploy-keys` e rodar de novo, ou trocar à mão na API)
- [ ] Remover `JWT_PRIVATE_KEY` do Vercel (o `deploy.sh` novo faz isso)
- [ ] Trocar a senha do owner em toda instância semeada com um dos valores antigos, incluindo o secret `DEMO_OWNER_PASSWORD`

### PR — `fix(security): papéis nas rotas próprias, ip confiável e chave privada fora do web`

Fecha o que ficou aberto dos PRs 41 e 44.

**Problemas:**
1. Rotas `/api/v1/*` aceitavam qualquer JWT válido: viewer salvava rascunho, publicava e fazia rollback. Os scopes `agent_os:write`/`agent_os:read` dos papéis não existem no RBAC do Agno, então editor e viewer também não acessavam as rotas do AgentOS (nem o modo teste).
2. `get_client_ip` confiava no primeiro valor de `X-Forwarded-For`, controlado pelo cliente: força bruta de senha sem limite trocando o header. O BFF não repassava o IP real, então todo login pelo painel caía no mesmo bucket (5 erros por minuto travavam todo mundo), e o `EXPIRE` renovado a cada tentativa nunca deixava a janela expirar.
3. PR 41 incompleto: `deploy.sh` e `bootstrap.sh` mandavam a chave privada ao web, e `web/src/lib/bff/token.ts` (morto) ainda a carregava. O web nunca recebia `JWT_PUBLIC_KEY`, que o proxy exige.

**O que mudou:**
- `api/app/authz.py`: dependência `require_scopes` com o casamento de scopes do Agno; scopes próprios `configs:read`, `configs:write`, `configs:publish`, `metrics:read` aplicados em todos os routers `/api/v1`
- `ROLE_SCOPES` remapeado para scopes reais (tabela em `api/README.md`)
- `TRUSTED_PROXIES` (settings): `X-Forwarded-For` só vale vindo de proxy listado, lido da direita para a esquerda
- Login limitado por e-mail (5/min) e por IP (20/min); Redis usa `EXPIRE NX`
- BFF: login repassa o IP do cliente; proxy genérico descarta `cookie` e cabeçalhos de encaminhamento e recusa `v1/auth/login`
- `token.ts` removido; scripts, compose e `.env.example` passam só `JWT_PUBLIC_KEY` ao web

**Critério de aceite:** viewer recebe 403 em toda escrita de `/api/v1`; editor passa; `X-Forwarded-For` forjado de cliente direto não muda o bucket; nenhum script ou compose entrega `JWT_PRIVATE_KEY` ao web.

### Próximos PRs da fase

- [x] #67 — `fix(api)`: registro real de runs (status de erro e duração), dono da versão no modo teste, banco fora do event loop, agente publicado sem restart, extended thinking aplicado, índices por data e gate de cobertura fora das evals noturnas
- [x] `fix(infra)`: entrypoint com `exec "$@"`, web de dev só no override, porta 8000 fora do compose de produção
- [x] `fix(web)`: fonte (`--font-sans` circular), tema conforme `DESIGN.md`, versão ativa no histórico, confirmação de publicar/reverter, alterações não salvas, estados de erro
- [x] `refactor(web)`: componentes shadcn (Button, Tabs, Field, Sonner) e nova página de edição
- [x] `feat(web)`: gráficos no analytics e no desempenho do agente
- [x] `fix(security)` restante: argon2 contra hash fixo no login (sem enumeração por tempo), CSP no painel e HSTS no painel e na API atrás de proxy confiável, `/docs` só com `APP_ENV=development`, `.dockerignore` sem `.env`, senha do seed fora da linha de comando no `deploy.sh`, reset da demo limpando `agent_run` e as tabelas do Agno
- [x] revogação de token (`jti`): todo token leva `jti`, logout revoga a sessão (`revoked_token`) e o `demo-reset.yml` passa as credenciais pelo ambiente do SSH

---

## Fase 12 — Multi-agente e MCP

Decisões em [ADR-0009](adr/0009-superficie-de-integracao.md), [ADR-0010](adr/0010-servidores-mcp-externos.md) e [ADR-0011](adr/0011-times-versionados.md). Depende do `fix(api)` de runtime da Fase 11 (#67). Cada PR é empilhado sobre o anterior: #67 a #76 já mergeados (em cascata nas branches); #77 leva tudo à `main`; #78 vem depois.

- [x] #68 — `docs(adr)`: ADR-0010, ADR-0011 e ADR-0009 aceito
- [x] #69 — `feat(api)`: cadastro de servidores MCP com segredo cifrado e proteção de SSRF (inclui lista única de routers para `main.py` e o export do OpenAPI, que agora traz `/auth`)
- [x] #70 — `feat(api)`: teste de conexão e descoberta de tools
- [x] #71 — `feat(api)`: agentes usam tools MCP na factory (payload v2)
- [x] #72 — `feat(web)`: catálogo de servidores MCP e seleção de tools no agente
- [x] #73 — `feat`: confirmação humana de tools sensíveis
- [x] #74 — `feat(api)`: times versionados e `TeamFactory`
- [x] #75 — `feat(web)`: editor de time e modo teste com rastro de delegação
- [x] #76 — `feat`: integrações — tokens de consumidor e catálogo exposto via `/mcp`
- [x] #78 — `feat`: árvore de execução

Fica para depois: workflows (condições guardadas no banco exigem `cel-python`), agendamentos (a factory recebe o run sem claims do usuário), guardrails por agente e A2A (exige `a2a-sdk` e não lista agentes de factory).

---

## Fase 13 — RAG (bases de conhecimento)

Decisão em [ADR-0012](adr/0012-bases-de-conhecimento.md). Base de conhecimento é cadastro próprio, não versionado; o agente versiona só a ligação (`knowledge: [{base_id, max_results}]` no payload). Conteúdo e vetores no Agno (`Knowledge` + `PgVector`, tabela por base no schema `ai`), por rotas próprias em `/api/v1/knowledge-bases`. Embeddings da Voyage (`voyage-3.5`) por padrão, OpenAI como alternativa. #85 e #86 contra a `main`; #87 a #94 empilhados (base = branch do anterior), mergear na ordem com "Delete branch".

- [x] #85 — `docs(adr)`: ADR-0012 e esta seção
- [x] #86 — `chore(infra)`: Postgres com pgvector (`pgvector/pgvector:pg17` nos compose e nos testes), migration `CREATE EXTENSION vector`, dependências (`pgvector`, `voyageai`, `pypdf`, `python-docx`, `beautifulsoup4`) e settings (`VOYAGE_API_KEY`, embedder padrão, limites de upload)
- [x] #87 — `feat(api)`: cadastro de bases (`knowledge_base`, CRUD, papéis: editor escreve, viewer lê)
- [x] #88 — `feat(api)`: ingestão de arquivo, URL e texto em background, com status, remoção, limites e SSRF na URL
- [x] #89 — `feat(api)`: busca de teste na base (trechos e score, sem rodar agente)
- [x] #90 — `feat(api)`: agentes e times usam bases (payload, factory, uma tool por base, bloco fixo nas instruções, aviso no linter, embedder determinístico no `DEMO_REPLAY`)
- [x] #91 — `feat(web)`: página Conhecimento (bases, upload com arrastar e soltar, status, remoção, busca de teste)
- [x] #92 — `feat(web)`: seleção de bases no agente e no time, e citações no modo teste e na árvore de execução
- [x] #93 — `feat`: custo de embedding no metering, no estimador e no analytics
- [x] #94 — `test(api)`: evals de recuperação (pergunta com documento esperado entre os primeiros resultados) e seed da demo com base

**Critério de aceite da fase:** subir um PDF numa base, ligar a base a um agente, publicar e ver no modo teste uma resposta que cita o documento; remover o documento e a resposta deixar de citá-lo.

Fica para depois: conectores remotos (S3, SharePoint, GitHub, já no Agno), reranker, filtros escolhidos pelo modelo (`enable_agentic_knowledge_filters`), reindexação agendada de URL e worker de ingestão separado.

---

## Fase 14 — Guardrails por agente

Decisão em [ADR-0013](adr/0013-guardrails-por-agente.md). Guardrails entram no payload versionado do agente (`guardrails`), viram `pre_hooks` e `post_hooks` do Agno na factory e são implementações próprias de `BaseGuardrail`: os prontos do Agno só têm padrões dos EUA e lista de injeção em inglês. Run bloqueado ganha status `blocked` e motivo em `agent_run`, fora da taxa de falha. #95 contra a `main`; #96 a #103 empilhados (base = branch do anterior), mergear na ordem com "Delete branch". O #97 (gestão de usuários) entrou antes: a migration de runs bloqueados é a `0017`.

- [x] #95 — `docs(adr)`: ADR-0013 e esta seção
- [x] #96 — `feat(api)`: seção `guardrails` no payload e regras de entrada — dados pessoais (CPF e CNPJ com dígito verificador, cartão com Luhn, e-mail, telefone BR; bloquear ou mascarar, mascarando também o input gravado quando bloqueia), injeção de prompt em PT e EN com termos extras, tópicos proibidos, tamanho máximo e moderação opcional da OpenAI (400 ao salvar sem `OPENAI_API_KEY`); factory aplica no agente, no líder e nos membros; mensagem de bloqueio configurável
- [x] #98 — `feat(api)`: status `blocked` e `blocked_by` em `agent_run` (migration), tracking lendo o `error_id` do bloqueio no stream e no não-stream, analytics e métricas por agente separando bloqueio de falha
- [x] #99 — `feat(api)`: guardrail de saída (dados pessoais e termos proibidos na resposta); troca a resposta no não-stream e marca o run no stream
- [x] #101 — `feat(web)`: seção Guardrails na aba Configuração do agente e do time, com aviso sobre moderação e sobre saída em stream; modo teste mostra qual regra bloqueou
- [x] #102 — `feat(web)`: bloqueios por motivo no analytics, no desempenho do agente e na lista de execuções
- [x] #103 — `test(api)`: evals de guardrails — casos de PII brasileira, injeção em PT e EN e falsos positivos conhecidos (número de pedido, "prompt do sistema" em contexto legítimo)

**Critério de aceite da fase:** ligar dados pessoais em modo bloquear num agente, publicar, mandar uma mensagem com CPF válido e ver o bloqueio no modo teste com o motivo, sem token gasto, com a sessão gravada mascarada e o run contado em bloqueios, não em falhas; a mesma mensagem com um número de pedido de 11 dígitos passa.

Fica para depois: classificador por LLM (tópico, toxicidade, injeção) como regra opcional, padrão de guardrails da instância e guardrails nos documentos indexados pelo RAG.

---

## Fase 15 — Workflows por etapas

Decisão em [ADR-0014](adr/0014-workflows-por-etapas.md). Workflow é um config com `kind = "workflow"`: uma árvore de etapas (agente ou time publicado), paralelos, condições e loops, versionada como agente e time. Condições usam regras próprias (contém, não contém, começa com, vazio, sobre a mensagem ou a etapa anterior), sem CEL. Etapa com erro para o fluxo, salvo se marcada para seguir. Sequência autorizada pelo usuário.

- [x] #108 — `docs(adr)`: ADR-0014 e esta seção
- [x] #109 — `feat(api)`: kind workflow, seção `workflow` no payload, regras e validação na escrita
- [x] #110 — `feat(api)`: `WorkflowFactory`, registro sem restart e erro de etapa que para o fluxo
- [x] #111 — `feat(api)`: run do workflow em `agent_run`, etapas com `parent_run_id` e consumo somado
- [x] #112 — `feat(web)`: página Workflows com editor de etapas. Lista e criação em `/workflows`; o editor monta a árvore (etapa, paralelo de 2 a 5 ramos, condição com então e senão, repetição com limite e regra de parada), só oferece contêiner onde o aninhamento ainda cabe e avisa antes de salvar o que a API recusaria. Cada etapa escolhe entre a versão vigente e uma versão publicada fixa do agente ou time; trocar o executor solta a versão fixada
- [x] #113 — `feat(web)`: modo teste com progresso por etapa e execuções do workflow. O painel lê o stream do AgentOS (`StepStarted`/`StepCompleted`, `*ExecutionStarted/Completed` dos contêineres, `RunStarted` e `RunError` com `step_name`) e mostra cada etapa com quem respondeu, a saída, o resultado da condição, a volta da repetição e a etapa que falhou ou foi bloqueada. O `nested_depth` do Agno vem 0 dentro de paralelo, então a indentação sai da pilha de contêineres abertos. As execuções do workflow mostram etapas, tokens e custo somados
- [x] #114 — `test(api)`: evals de workflows e seed da demo. `test_evals_workflows.py` cobre regras com textos reais (inclusive os limites de negação e flexão), condição depois de paralelo, parada de repetição e estrutura. O seed cria o workflow do critério de aceite sobre os agentes da demo; o `seed_analytics` deixa workflows de fora, porque o consumo deles é o das etapas

**Critério de aceite da fase:** montar um workflow com triagem, um paralelo de duas análises, uma etapa de consolidação e uma condição que só roda a revisão quando a resposta menciona "reembolso"; publicar, rodar no modo teste e ver cada etapa na árvore de execução, com o run do workflow somando o consumo das etapas; um agente com erro na triagem para o fluxo e o run aparece como falha.

Fica para depois: pausa humana no meio do fluxo, CEL como modo avançado, roteador e mapeamento de entrada por etapa.

---

## Fase 16 — Evals por agente no painel

Decisão em [ADR-0015](adr/0015-evals-por-agente.md). Cada agente e time ganha uma suíte de casos (entrada e checagens de texto, de tools chamadas e por juiz LLM), fora do payload versionado. A suíte roda em background com o runner de suíte do Agno (`agno.eval.suite`) contra qualquer versão: rascunho, vigente ou publicada. A comparação mostra regressões entre versões, e um gate opcional exige suíte verde no rascunho para publicar. Os runs de eval ficam fora das métricas de conversa, e o custo deles aparece separado.

- [x] #118 — `docs(adr)`: ADR-0015 e esta seção
- [x] `feat(api)`: casos de teste por config, checagens validadas na escrita e CRUD em `/api/v1/configs/{id}/eval-cases`. Tabela `eval_case` (migration 0019), scopes `evals:read`, `evals:write` e `evals:run`
- [x] `feat(api)`: execução da suíte em background com o runner do Agno, resultado por caso e runs de eval marcados fora do analytics. Tabelas `eval_run` e `eval_result` e `eval_run_id` em `agent_run` e `usage_event` (migration 0020)
- [x] `feat(api)`: juiz com modelo escolhido e medido, custo da execução e checagem de juiz "não avaliada" no modo demo. O medidor embrulha o `ainvoke` do modelo do juiz; `eval_run` ganha `judge_model`, `total_tokens` e `cost` (migration 0021), e o resumo do analytics ganha `eval_tokens` e `eval_cost`
- [x] `feat(api)`: comparação entre versões e gate de publicação por suíte verde. Comparação caso a caso em `/eval-runs/compare`; flag `require_passing_evals` no `agent_config` (migration 0022) e configuração em `/eval-settings`; rollback fica fora do gate
- [x] `feat(web)`: aba Testes no agente e no time, com casos, execução, resultado por caso e regressões. Aba Testes no agente e Suíte no painel lateral do time; editor de casos com as três checagens, juiz entre os modelos com saída estruturada, acompanhamento da execução por polling, comparação vigente × rascunho e chave do gate
- [x] `feat(web)`: publicação mostra o resultado da suíte e respeita o gate. A aba Versões do agente e do time resume a última execução no rascunho, desabilita Publicar quando o gate bloqueia e mostra a mensagem do 409
- [x] `test(api)`: evals da avaliação (scorer de texto e montagem dos casos) e suíte de exemplo no seed da demo. `test_evals_suite.py` sem banco nem LLM; o seed cria quatro casos no atendimento, e o reset da demo limpa as tabelas de eval

**Critério de aceite da fase:** no agente de atendimento, montar cinco casos: dois de texto, um que exige `buscar_politicas_atendimento` e dois por juiz. Rodar no rascunho e na vigente. Mudar o prompt de um jeito que quebre um caso e ver a regressão apontada caso a caso. Com o gate ligado, a publicação é recusada até a suíte passar no rascunho atual. Os runs de teste não aparecem nas conversas do analytics, e o custo deles aparece separado.

Fica para depois: suíte em workflow, caso que espera bloqueio de guardrail, execução agendada, execução disparada por token de integração (CI de quem consome o agente) e geração de casos a partir de conversas reais.


---

## Fase 17 — Evals contínuos

Decisão em [ADR-0016](adr/0016-evals-continuos.md). A suíte da Fase 16 deixa de depender do botão Rodar: tokens de integração disparam e consultam a suíte dos agentes e times liberados, um agendamento por config roda a suíte contra a vigente, e conversas reais viram casos de teste revisados, com dados pessoais mascarados. Regressão agendada aparece na lista de agentes e na aba Testes. Casos podem trazer até cinco mensagens anteriores como contexto, rodadas na mesma sessão com o `setup` e o `session_id` do `Case` da v3.

Pré-requisito: Agno 3.1.x (#128 e #129).

- [x] #127 — `docs(adr)`: ADR-0016 e esta seção
- [ ] `feat(api)`: origem e alvo por apelido na execução da suíte. `trigger` e `target` no `eval_run`, `verdict` no resumo
- [ ] `feat(api)`: tokens de integração disparam e consultam a suíte. Escopos `evals:<id>:run` e `evals:<id>:read` por config na emissão, checagem por recurso nas rotas de execução
- [ ] `feat(api)`: agendamento da suíte com poller próprio. Tabela `eval_schedule`, cron e fuso com `agno.scheduler.cron`, reivindicação com `SKIP LOCKED`, intervalo mínimo de 1 hora, desligado no modo demo
- [ ] `feat(api)`: casos com turnos anteriores. `context` no `eval_case` (até cinco mensagens), rodado no `setup` do `Case` no mesmo `session_id`, e `user_id` do caso no lugar da troca pela `ContextVar`
- [ ] `feat(api)`: estado da suíte e regressão agendada. Comparação com a execução agendada anterior e estado da suíte na lista de configs
- [ ] `feat(api)`: sugestão de caso a partir de um run real. Leitura em `agno_runs`, entrada e contexto mascarados, tools chamadas e critério de rascunho, `source_run_id` no `eval_case`
- [ ] `feat(web)`: agendamento e origem das execuções na aba Testes, estado da suíte na lista, suíte na emissão de tokens de integração
- [ ] `feat(web)`: "Virar caso de teste" no histórico de execuções e na árvore de execução
- [ ] `test(api)`: evals do agendamento, do escopo por recurso e da sugestão de caso, e exemplo de job de CI na documentação

**Critério de aceite da fase:**

- Um token de integração liberado só para o agente de atendimento dispara a suíte na vigente e lê `verdict` até a execução terminar. O mesmo token recebe 403 na suíte de outro agente e na edição de casos.
- Um agendamento diário roda sozinho, com origem "agendada", e duas réplicas da API não duplicam a execução.
- Com uma mudança na base de conhecimento que quebra um caso, a execução agendada seguinte aparece como regressão na lista de agentes.
- Uma conversa com CPF no histórico vira caso com `[CPF removido]` no lugar do número, com os turnos anteriores como contexto e com a tool que o run chamou já marcada.
- Um caso com duas mensagens de contexto só passa se o agente usar o que foi dito antes; sem o contexto, o mesmo caso falha.

Fica para depois: aviso de regressão por webhook ou e-mail, suíte em workflow, caso que espera bloqueio de guardrail e geração automática de casos em lote a partir das conversas.
