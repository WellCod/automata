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

```bash
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

## Scopes JWT

Documentados quando o PR de autorização for mergeado (PR 11).
