# Automata — instruções para Claude Code

## Protocolo de trabalho

Um PR por vez. Abre branch, implementa, abre o PR como draft e para. Não começa o próximo antes de aprovação explícita ("prossiga").

Antes de qualquer PR da API, confirma assinatura de classe/parâmetro do Agno na doc — a versão muda rápido.

## Commits

Conventional commits com escopo em português:

```
feat(config): adiciona suporte a rollback de versão
fix(linter): corrige falso positivo em guardrails
chore(ci): ajusta filtro de paths no gate job
```

Regras:
- Assunto: minúscula, sem ponto final, imperativo
- Corpo apenas quando o "por quê" não é óbvio pelo diff
- **Sem** `Co-Authored-By` ou qualquer trailer de ferramenta
- **Sem emoji** em mensagens de commit
- Não uniformize tamanho — mudança trivial leva uma linha

## Pull requests

- Nome de branch: `feat/`, `fix/`, `chore/`, `test/`, `refactor/`
- Abra como draft enquanto incompleto
- Descrição proporcional ao PR — PR pequeno não leva seções em negrito
- Link o ADR relevante quando a decisão já estiver registrada
- Se o PR contradiz um ADR, avisa antes de abrir

## Escrita

Commits, PRs, comentários e README em português. Direto, sem preâmbulo. Como engenheiro anotando para colega.

Evite: "vamos", "vale notar que", "em resumo", comentário que repete o código, docstring em função trivial.

## Stack

- Python 3.12, uv, agno[os]==2.8.7, Postgres, Alembic, pydantic-settings
- mypy strict + plugin pydantic, ruff (E, F, I, UP, B, SIM)
- pytest com pytest-asyncio, testcontainers para integração
- Rotas próprias em router com prefixo `/api/v1`, nunca modificar rotas do AgentOS

## Sequência de PRs — Fase 1

- [x] PR 4 — `chore(api): scaffolding do projeto python`
- [x] PR 5 — `feat(api): sobe o agentos com postgres`
- [x] PR 6 — `feat(config): schema e migration da configuração versionada`
- [x] PR 7 — `feat(config): rascunho, publicação e rollback`
- [x] PR 8 — `feat(agents): factory e resolução de modelo`
- [x] PR 9 — `feat(agents): matriz de capabilities e validação na escrita`
- [x] PR 10 — `feat(linter): linter de prompt`
- [x] PR 11 — `feat(api): autorização jwt e scopes`
- [x] PR 12 — `feat(metering): rollup de consumo por período`
- [x] PR 13 — `test(api): evals de confiabilidade no ci`
