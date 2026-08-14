# Automata

[![CI](https://github.com/WellCod/automata/actions/workflows/ci.yml/badge.svg)](https://github.com/WellCod/automata/actions/workflows/ci.yml)
[![Publish](https://github.com/WellCod/automata/actions/workflows/publish.yml/badge.svg)](https://github.com/WellCod/automata/actions/workflows/publish.yml)

Plataforma de operação de agentes de IA em produção — versionamento imutável de configuração, rollback em um clique, troca de modelo sem reescrita de prompt, estimativa de custo antes de publicar e painel analítico com latência p50/p95 por agente.

---

## Demo

**Sem credencial de LLM.** O modo `DEMO_REPLAY=true` substitui o provider real por respostas pré-gravadas em `api/fixtures/`. Versionamento, rollback, modo teste e analytics funcionam completamente offline.

```bash
# 1. Sobe com replay
DEMO_REPLAY=true docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2. Seed: owner + 5 agentes publicados + 500 runs históricos (90 dias)
docker exec \
  -e SEED_OWNER_EMAIL="admin@automata.dev" \
  -e SEED_OWNER_PASSWORD="Automata2024!" \
  automata-api-1 bash -c "cd /app && .venv/bin/python scripts/seed.py full"

# 3. Painel
pnpm --filter web dev   # http://localhost:3000
```

Login: `admin@automata.dev` / `Automata2024!`

O seed `full` gera 5 agentes com perfis distintos (Analista Financeiro em `claude-opus-4-7`, Redator em `claude-sonnet-4-6`, Atendimento e Suporte em `claude-haiku-4-5`, Assistente de Código em `claude-sonnet-4-6`) e distribui 500 execuções nos últimos 90 dias com latências, taxas de erro e custos proporcionais ao modelo de cada agente. O painel de analytics reflete dados realistas desde o primeiro acesso.

Guia completo em [`DEMO.md`](DEMO.md).

---

## O problema

Colocar um agente de IA em produção é simples. Operar quarenta, com equipes diferentes editando prompts, é outro problema.

**Prompt sem histórico.** Alguém ajusta uma instrução às 18h, a qualidade cai — e não há caminho de volta. O prompt estava num campo de texto que foi sobrescrito.

**Troca de modelo quebra comportamento silenciosamente.** Instruções acopladas a um provider específico (blocos de raciocínio, formato JSON sem markdown) degradam ao migrar de modelo sem gerar erro visível.

**Custo opaco até a fatura chegar.** Sem estimativa antes de publicar, um prompt de três mil tokens multiplicado pelo volume mensal pode estourar o contrato sem nenhum alerta.

**Configuração e prompt divergem.** O prompt menciona uma ferramenta que não está habilitada no agente. Isso não falha no deploy — falha na conversa com o usuário, dias depois.

Automata trata esses quatro problemas como requisito de produto, não como disciplina de quem edita.

---

## O que está implementado

### Gestão de configuração

| Funcionalidade | Detalhe |
|---|---|
| **Versionamento imutável** | Publicar cria uma `AgentConfigVersion` e move um ponteiro. A versão anterior nunca é alterada. |
| **Rollback em um clique** | Mover o ponteiro para qualquer versão anterior — sem redeploy, sem reescrita. |
| **Diff visual entre versões** | Comparação lado a lado de instruções, modelo e capabilities entre versões. |
| **Factory por request** | O agente é reconstruído a partir da versão vigente em cada chamada — editar comportamento não exige redeploy. |
| **Modo teste** | Chat integrado no painel executa o agente na versão de rascunho, sem publicar. |

### Qualidade antes de publicar

| Funcionalidade | Detalhe |
|---|---|
| **Linter de prompt** | Detecta referências a ferramentas não habilitadas e termos acoplados a provider. Alerta inline na edição. |
| **Estimativa de custo** | Tokens estimados, custo por mensagem e projeção por volume — visíveis enquanto se edita. |
| **Capabilities condicionais** | Extended thinking, structured output e tool use são habilitadas por modelo. O campo é desativado e explicado se o modelo escolhido não suportar. |
| **Validação na escrita** | Capabilities solicitadas mas não suportadas pelo modelo bloqueiam o save — não chegam a produção. |
| **Instructions agnósticas de provider** | Validação recusa instruções com termos acoplados a provider específico. Garantida por teste no CI ([ADR-0006](docs/adr/0006-instructions-agnosticas-de-provider.md)). |

### Observabilidade e analytics

| Funcionalidade | Detalhe |
|---|---|
| **Painel Analytics global** | Volume de runs, tokens consumidos, custo total e latência p50/p95 — com filtro por período e intervalo de datas customizado. |
| **Métricas por agente** | Tabela com distribuição de runs, latência mediana e taxa de erro por agente e modelo. |
| **Histórico de execuções** | Lista de runs com status, latência, tokens e custo por execução. Atualização em tempo real via SSE. |
| **Logging estruturado** | Todos os logs incluem `request_id` correlacionável. Formato JSON em produção. |
| **Health check com validação de banco** | `/api/v1/health` verifica conectividade real com o Postgres antes de responder `healthy`. |

### Segurança e autenticação

| Área | Implementação |
|---|---|
| **JWT RS256** | Chave privada gerada localmente via OpenSSL. Nunca enviada ao browser. |
| **BFF pattern** | Todos os requests ao AgentOS passam por Route Handlers server-side do Next.js. O token não toca o client-side. |
| **Papéis e scopes** | `owner`, `editor`, `viewer` — cada endpoint do AgentOS exige scope específico. |
| **Política de senha** | Comprimento mínimo, caracteres especiais, maiúscula e número — validados na API. |
| **Headers de segurança** | `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy`. |
| **Rate limiting** | Distribuído via Redis — limite por IP com burst configurável. |
| **Secrets fora do bundle** | Teste no CI inspeciona o bundle compilado do Next.js à procura de padrões de chave. Build falha se encontrar. |

### Confiabilidade e performance

| Área | Implementação |
|---|---|
| **Pool de conexões compartilhado** | SQLAlchemy Engine criado uma vez e reusado. Configurado com `pool_size`, `max_overflow` e `pool_pre_ping`. |
| **Índices de banco** | Índices em `agent_run(config_id, started_at)` e `usage_event(config_id, recorded_at)` — as duas colunas usadas em todos os filtros de analytics. |
| **Cache HTTP em capabilities** | Endpoint `/capabilities` retorna `Cache-Control: public, max-age=300`. |
| **Reconnect de MCP Tools** | Factory recupera a conexão de MCP Tools antes de cada execução, eliminando falhas por sessão expirada. |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────┐
│  web/  — Next.js 16, App Router, React 19           │
│  TypeScript strict · shadcn/ui · TanStack Query 5   │
│  Vitest · Playwright E2E · bundle secrets test       │
└──────────────────────────┬──────────────────────────┘
                           │  BFF: Route Handlers server-side
                           │  (JWT RS256 — chave privada nunca
                           │   sai do servidor)
┌──────────────────────────┴──────────────────────────┐
│  api/  — FastAPI, Python 3.12                       │
│  AgentConfigVersion · factory por request           │
│  linter · estimativa de custo · metering            │
│  JWT RS256 · scopes · migrations próprias           │
│  logging estruturado · health check · rate limit    │
└──────────────────────────┬──────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────┐
│  Agno 2.8.7 (AgentOS)                               │
│  REST · sessions · traces · scopes por endpoint     │
└──────────────────────────┬──────────────────────────┘
                           │
              ┌────────────┴────────────┐
         PostgreSQL 17              Redis
         (config + runs           (rate limiting
          + metering)              distribuído)
```

O agente não é um objeto estático em código. Ele é construído por request a partir da versão publicada da configuração — isso permite editar comportamento sem redeploy e executar qualquer versão histórica em modo teste.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Runtime de agente | Agno 2.8.7 (AgentOS) — FastAPI integrado, JWT com scopes, traces e sessions persistidos |
| API | Python 3.12, `uv` — lockfile determinístico, mypy strict, ruff (E/F/I/UP/B/SIM) |
| Banco | PostgreSQL 17, Alembic — migrations isoladas das tabelas do framework |
| Cache / Rate limit | Redis — rate limiting distribuído com burst por IP |
| Painel | Next.js 16, TypeScript strict, Tailwind 4, shadcn/ui |
| Estado e fetch | TanStack Query 5, openapi-fetch — tipos gerados via openapi-typescript, nunca escritos à mão |
| Formulários | react-hook-form + zod — habilitação condicional de campos requer schema declarativo |
| Testes API | pytest + asyncio, testcontainers — integração sem mock de banco; evals do Agno nightly |
| Testes Web | Vitest + Testing Library, Playwright E2E — inclui teste de secrets no bundle compilado |
| CI/CD | GitHub Actions — cache de layers Docker, coverage gate 70%, publish para GHCR |

---

## Decisões de arquitetura

Cada decisão relevante está documentada em [`docs/adr/`](docs/adr/) com contexto, alternativas descartadas (e por quê) e o gatilho concreto que faria reverter. As mais relevantes para entender o desenho:

| ADR | Decisão |
|---|---|
| [ADR-0001](docs/adr/0001-monorepo.md) | Monorepo sem ferramenta de monorepo — `uv` e `pnpm` bastam para duas aplicações em linguagens diferentes |
| [ADR-0002](docs/adr/0002-config-em-banco-proprio.md) | Config em banco próprio — por que não usar o editor visual do framework como fonte da verdade |
| [ADR-0003](docs/adr/0003-single-tenant.md) | Deploy single-tenant — por que uma instância por cliente, e a assimetria que torna difícil desfazer |
| [ADR-0005](docs/adr/0005-auth-jwt-proprio.md) | Auth JWT RS256 próprio — a chave de assinatura nunca sai do servidor |
| [ADR-0006](docs/adr/0006-instructions-agnosticas-de-provider.md) | Instructions agnósticas de provider — a regra que sustenta a promessa de trocar modelo |

---

## Testes

```bash
# API — suite completa (sem LLM real, usa testcontainers)
cd api && uv run pytest -m "not nightly"

# API — evals de confiabilidade com LLM real (nightly no CI)
cd api && uv run pytest -m nightly   # requer ANTHROPIC_API_KEY

# Web — unitários e de componente
pnpm --filter web test

# Web — E2E (fluxo: login → editar agente → publicar → rollback)
pnpm --filter web test:e2e
```

Coverage gate: 70% no CI. O build falha se cair abaixo.

---

## Rodando local

**Pré-requisitos:** Docker Desktop, Node.js 22+, pnpm 11+, Python 3.12+, `uv`, `openssl`

```bash
git clone https://github.com/WellCod/automata.git
cd automata
bash scripts/bootstrap.sh   # gera chaves RSA, cria .env, instala deps e sobe o banco
```

**Terminal 1 — API:**
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

API disponível em `http://localhost:8000`. Migrations rodam automaticamente no boot.

**Terminal 2 — Painel:**
```bash
pnpm --filter web dev   # http://localhost:3000
```

**Seed:**
```bash
# Mínimo: só cria o owner
docker exec \
  -e SEED_OWNER_EMAIL="admin@exemplo.com" \
  -e SEED_OWNER_PASSWORD="Senha123!" \
  automata-api-1 bash -c "cd /app && .venv/bin/python scripts/seed.py minimal"

# Demo completo: 5 agentes + 500 runs históricos
docker exec \
  -e SEED_OWNER_EMAIL="admin@exemplo.com" \
  -e SEED_OWNER_PASSWORD="Senha123!" \
  automata-api-1 bash -c "cd /app && .venv/bin/python scripts/seed.py full"
```

---

## Estrutura

```
api/
  app/          aplicação FastAPI
  alembic/      migrations do banco próprio
  fixtures/     respostas pré-gravadas para DEMO_REPLAY=true
  scripts/      seed (minimal|demo|full), export_openapi
  tests/        pytest: integração + evals nightly
web/
  src/app/      rotas e Route Handlers (BFF)
  src/components/
  src/lib/      client openapi-fetch, hooks, utils
docs/adr/       9 Architecture Decision Records
DEMO.md         guia de demo local sem credencial de LLM
```

---

## Licença

Ver [`LICENSE`](LICENSE). Justificativa em [ADR-0007](docs/adr/0007-licenciamento.md).

---

Construído sobre [Agno](https://github.com/agno-agi/agno). Nenhum dado de produção, prompt real ou identificação de cliente consta neste repositório.
