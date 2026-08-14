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

## Fase 2 — Painel

Stack: Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, TanStack Query, react-hook-form + zod, openapi-typescript, Vitest + Testing Library, Playwright, ESLint, Prettier.

Regras críticas:
- Nunca `NEXT_PUBLIC_*` para token, chave ou segredo
- Todo acesso ao AgentOS via Route Handlers server-side (BFF)
- Tipos do client são gerados, nunca escritos à mão
- Sem `any`, sem `@ts-ignore` sem comentário justificando

## Sequência de PRs — Fase 2

- [x] PR 14 — `chore(web): scaffolding do painel`
- [x] PR 15 — `feat(web): bff e tipos gerados do openapi`
- [x] PR 16 — `feat(web): lista de agentes`
- [x] PR 17 — `feat(web): formulário de edição, campos base`
- [x] PR 18 — `feat(web): seletor de modelo com capabilities condicionais`
- [x] PR 19 — `feat(web): painel do linter`
- [x] PR 20 — `feat(web): estimador de custo`
- [x] PR 21 — `feat(web): versões, diff e rollback`
- [x] PR 22 — `feat(web): modo teste a partir do agent-ui`
- [x] PR 23 — `test(web): e2e do fluxo crítico`

## Sequência de PRs — Fase 3

- [x] PR 24 — `feat(api): usuários, papéis e emissão de token`
- [x] PR 25 — `feat(web): login e sessão`
- [x] PR 26 — `feat(api): seed de instância`
- [x] PR 27 — `chore: imagem versionada e publicação`
- [x] PR 28 — `feat(demo): modo replay de inferência`
- [x] PR 29 — `chore(demo): deploy e reset periódico`
- [x] PR 30 — `docs: link da demo e credenciais de acesso`

## Fase 4 — Segurança

Derivada de auditoria técnica em 2026-08-12. Detalhes em `docs/roadmap.md`.

- [x] PR 41 — `fix(security): remove jwt_private_key do container web`
- [x] PR 42 — `fix(security): validação jwt no proxy bff e cookie secure`
- [x] PR 43 — `fix(security): headers de segurança http`
- [x] PR 44 — `fix(security): política de senha, csrf e ip forwarding`

## Fase 5 — Estabilidade e Performance

- [x] PR 45 — `fix(api): pool de conexões sqlalchemy compartilhado`
- [x] PR 46 — `chore(infra): restart policies, resource limits e health check`
- [x] PR 47 — `feat(api): índices de banco e cache http em capabilities`

## Fase 6 — Observabilidade

- [x] PR 48 — `feat(api): logging estruturado com request-id`
- [x] PR 49 — `feat(api): health check com validação de banco`

## Fase 7 — Qualidade e CI/CD

- [x] PR 50 — `chore(ci): testes de integração, coverage e cache de layers docker`
- [x] PR 51 — `feat(infra): redis e rate limiting distribuído`
- [x] PR 52 — `chore(dev): script de bootstrap e env de desenvolvimento`

## Fase 8 — Agentes Vivos

Fecha o gap de factories vazias e adiciona visibilidade de execução. Detalhes em `docs/roadmap.md`.

- [x] PR 54 — `feat(api): carregamento dinâmico de factories a partir de configs publicados`
- [x] PR 55 — `feat(api): router de runs — histórico e status por agente`
- [x] PR 56 — `feat(web): painel de runs em tempo real com SSE`
- [x] PR 57 — `feat(api): métricas por agente — p50/p95 de latência e taxa de erro`
- [x] PR 58 — `fix(api): reconexão de MCPTools e validação de escopo em /mcp`

## Fase 9 — Analytics

Painel analítico consolidado aproveitando `agent_run` e `usage_event` já persistidos.

- [x] PR 59 — `feat(web): painel analytics global — runs, latência, custo e tokens`
