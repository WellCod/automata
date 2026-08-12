# automata — api

API em Python sobre o Agno AgentOS.

## Dependências principais

| Pacote | Versão pinada | Licença |
|--------|--------------|---------|
| agno[os] | 2.8.7 | Apache 2.0 |
| psycopg[binary] | ≥3.2 | LGPL-3.0 |
| alembic | ≥1.14 | MIT |
| pydantic-settings | ≥2.7 | MIT |

A licença do Agno na versão 2.8.7 é **Apache 2.0**, confirmada em `github.com/agno-agi/agno/blob/main/LICENSE`. ADR-0007 registrava incerteza entre MPL-2.0 e Apache-2.0 — resolvida: é Apache 2.0, compatível com AGPL-3.0 para fins de distribuição.

## Rodando local

Para desenvolvimento, a API roda em Docker junto com o banco. A partir da raiz do repositório:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

A API sobe em `http://localhost:8000` com hot-reload ativo. As migrations rodam automaticamente no boot via `alembic upgrade head`.

Para rodar isolado (sem Docker), com banco já acessível via `DATABASE_URL`:

```bash
cd api
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Evals de confiabilidade

Dois níveis de cobertura:

| Suite | Quando roda | Como rodar |
|---|---|---|
| Smoke | Todo PR (CI) | `pytest -m "not nightly"` |
| Noturna | Diariamente às 03:00 UTC | `pytest -m nightly` |

A suite smoke testa a lógica do `ReliabilityEval` com `RunOutput` construído manualmente — sem custo e sem dependência de credencial. A suite noturna chama LLM real (Claude Haiku) e verifica que o agente chama as tools esperadas. Requer `ANTHROPIC_API_KEY` no ambiente.

Arquivos:
- `tests/test_evals_smoke.py` — fixtures gravadas, sem LLM
- `tests/test_evals_nightly.py` — evals com LLM real, marcados `@pytest.mark.nightly`
- `.github/workflows/evals-nightly.yml` — workflow agendado

## Metering

`GET /api/v1/usage/rollup?period=YYYYMM&agent_id=<uuid>` — retorna consumo agregado por agente no período.

Cada execução registra um `UsageEvent` via post_hook injetado pelo `AgentFactory`. O rollup agrega tokens e custo por `(agent_config_id, period)`. Campos: `run_count`, `input_tokens`, `output_tokens`, `total_tokens`, `cost`.

## Scopes JWT

Autenticação por JWT assimétrico RS256. O backend emite o token (via `app.auth.issue_token`), o AgentOS verifica usando a chave pública de `JWT_PUBLIC_KEY`. `user_isolation=True` ativo — cada usuário só enxerga suas próprias sessões e memórias.

| Scope | Descrição |
|---|---|
| `agent_os:admin` | Acesso total — todos os endpoints |
| `agents:read` | Listar e ler agentes |
| `agents:write` | Criar e editar agentes |
| `agents:*:run` | Executar qualquer agente |
| `agents:<id>:run` | Executar agente específico |
| `sessions:read` | Ver sessões |
| `sessions:write` | Criar e atualizar sessões |
| `sessions:delete` | Apagar sessões |
| `memories:read` | Ver memórias |
| `memories:write` | Criar e atualizar memórias |
| `memories:delete` | Apagar memórias |
| `traces:read` | Ver traces |
| `config:read` | Ler configuração da OS |
| `config:write` | Operações administrativas (ex: migrations) |
| `evals:read` | Ver execuções de evals |
| `evals:write` | Criar e atualizar evals |
| `service_accounts:read` | Listar service accounts |
| `service_accounts:write` | Emitir tokens de service account |

Rotas próprias (`/api/v1/*`) não estão no mapa de scopes do AgentOS — acessíveis com qualquer JWT válido, independente de escopo.

Chave privada (`JWT_PRIVATE_KEY`) usada apenas pelo BFF do painel (Next.js Route Handler) e pelos testes de integração. Nunca chega ao browser (ADR-0005).
