# Automata

[![CI](https://github.com/WellCod/automata/actions/workflows/ci.yml/badge.svg)](https://github.com/WellCod/automata/actions/workflows/ci.yml)
[![Publish](https://github.com/WellCod/automata/actions/workflows/publish.yml/badge.svg)](https://github.com/WellCod/automata/actions/workflows/publish.yml)

Plataforma de gestão de agentes de IA em produção: catálogo, edição versionada, troca de modelo sem reescrita de prompt e rastreio de custo por agente.

---

## Demo

**Sem credencial de LLM.** A demo usa `DEMO_REPLAY=true` — as respostas são pré-gravadas em `api/fixtures/` e o painel funciona normalmente. Edição, versionamento, modo teste e analytics rodam sem chamar nenhum provedor.

**Demo local em 3 passos:**

```bash
# 1. Sobe com modo replay
DEMO_REPLAY=true docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2. Seed completo: owner + 5 agentes + 500 runs históricos
docker exec \
  -e SEED_OWNER_EMAIL="admin@automata.dev" \
  -e SEED_OWNER_PASSWORD="Automata2024!" \
  automata-api-1 uv run python scripts/seed.py full

# 3. Painel
pnpm --filter web dev   # http://localhost:3000
```

Login: `admin@automata.dev` / `Automata2024!`

O seed `full` cria 5 agentes com instruções completas (Analista Financeiro, Redator de Conteúdo, Atendimento, Suporte Técnico, Assistente de Código) e 500 execuções distribuídas nos últimos 90 dias com latências, taxas de erro e custos proporcionais ao modelo de cada agente.

Guia completo em [`DEMO.md`](DEMO.md).

---

## O problema

Colocar um agente de IA em produção é fácil. Operar quarenta é outro problema.

**Prompt em produção não tem histórico.** Alguém ajusta uma instrução às 18h de sexta, a qualidade cai, e não existe caminho de volta. O prompt não está em código — está num campo de texto que foi sobrescrito.

**Trocar de modelo é reescrever prompt.** Instruções que dizem "responda em JSON sem markdown" ou que mencionam blocos de raciocínio estão acopladas a um provider específico. Trocar o modelo quebra o comportamento de forma silenciosa — a saída degrada, mas não dá erro.

**O custo é opaco até a fatura chegar.** Sem estimativa antes de publicar, não há como saber se um prompt de três mil tokens vezes o volume mensal cabe no contrato.

**A configuração e o prompt divergem.** O prompt menciona uma função que não está habilitada no agente. Isso não falha no deploy — falha na conversa com o usuário final, dias depois.

Automata trata esses quatro problemas como requisito de produto, não como disciplina de quem edita.

## Como resolve

**Versionamento imutável.** Publicar cria uma versão nova e move um ponteiro. Versão publicada nunca sofre alteração. Rollback é mover o ponteiro de volta — operação de um clique, não de um deploy.

**Modelo como campo.** O agente referencia um identificador de modelo, resolvido em tempo de execução. As instruções são validadas contra uma lista de termos acoplados a provider antes de publicar. A troca de modelo continua sendo um campo porque existe um teste garantindo isso.

**Capabilities validadas na escrita.** Se a configuração pede raciocínio estendido e o modelo escolhido não suporta, a validação recusa no momento de salvar — não em produção. O painel desabilita a opção e explica o motivo.

**Linter de prompt.** Função citada nas instruções e não habilitada no agente vira aviso na própria tela de edição, com ação para habilitar.

**Estimativa antes de publicar.** Tokens estimados, custo por mensagem e projeção por volume, visíveis enquanto se edita.

---

## Arquitetura

Três camadas, com fronteira clara de quem escreve o quê:

```
┌─────────────────────────────────────────────┐
│  web/  — painel Next.js                     │
│  lista · edição versionada · modo teste     │
└────────────────────┬────────────────────────┘
                     │  BFF: Route Handlers server-side
                     │  (JWT nunca chega ao browser)
┌────────────────────┴────────────────────────┐
│  api/  — FastAPI sobre Agno AgentOS         │
│  config versionada · factory · linter       │
│  metering · JWT RS256 · migrations próprias │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────┴────────────────────────┐
│  Agno SDK + AgentOS                         │
│  REST · scopes por endpoint · traces        │
└─────────────────────────────────────────────┘
```

O agente não é um objeto estático em código. Ele é construído por request a partir da versão vigente da configuração — isso permite editar comportamento sem redeploy e rodar uma versão específica em modo teste.

## Stack

| Camada | Tecnologia | Decisão |
|---|---|---|
| Runtime de agente | Agno 2.8.7 (AgentOS) | FastAPI integrado, JWT com scopes, traces e sessions persistidos |
| API | Python 3.12, `uv` | Resolução determinística com lockfile |
| Banco | PostgreSQL 17, Alembic | Migrations próprias, isoladas das tabelas do framework |
| Painel | Next.js 16, TypeScript strict, Tailwind, shadcn/ui | Tipos do client gerados via openapi-typescript — nunca escritos à mão |
| Formulários | react-hook-form + zod | Habilitação condicional de campos requer schema declarativo |
| Testes | pytest + asyncio, Vitest, Playwright | Evals do Agno para confiabilidade de tool call; testcontainers para integração |

Monorepo sem ferramenta de monorepo: `uv` e `pnpm` bastam para duas aplicações em linguagens diferentes. Justificativa em [ADR-0001](docs/adr/0001-monorepo.md).

## Decisões de arquitetura

A parte substantiva do projeto está em [`docs/adr/`](docs/adr/). Cada registro tem contexto, alternativas descartadas com o motivo específico, consequências — incluindo o que ficou pior — e o gatilho concreto que faria reverter.

Os mais relevantes para entender o desenho:

- [ADR-0002 — Config em banco próprio](docs/adr/0002-config-em-banco-proprio.md): por que não usar o editor visual do framework como fonte da verdade
- [ADR-0003 — Deploy single-tenant](docs/adr/0003-single-tenant.md): por que uma instância por cliente, e a assimetria que torna difícil desfazer
- [ADR-0005 — Auth JWT](docs/adr/0005-auth-jwt-proprio.md): por que a chave de assinatura nunca chega ao browser
- [ADR-0006 — Instructions agnósticas de provider](docs/adr/0006-instructions-agnosticas-de-provider.md): a regra que sustenta a promessa de trocar modelo

---

## Rodando local

**Pré-requisitos:** Docker Desktop, Node.js 22+, pnpm 11+, Python 3.12+, uv, openssl

```bash
git clone https://github.com/WellCod/automata.git
cd automata
bash scripts/bootstrap.sh   # gera chaves RSA, cria .env, instala deps e sobe o banco
```

**Terminal 1 — banco de dados e API:**
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

A API sobe em `http://localhost:8000`. As migrations rodam automaticamente no boot.

**Terminal 2 — painel:**
```bash
pnpm --filter web dev
```

O painel sobe em `http://localhost:3000`.

**Seed** (com os containers no ar):
```bash
# Mínimo: só cria o owner
docker exec -e SEED_OWNER_EMAIL="admin@exemplo.com" -e SEED_OWNER_PASSWORD="Senha123!" \
  automata-api-1 uv run python scripts/seed.py minimal

# Demo completo: owner + 5 agentes publicados + 500 runs de histórico
docker exec -e SEED_OWNER_EMAIL="admin@exemplo.com" -e SEED_OWNER_PASSWORD="Senha123!" \
  automata-api-1 uv run python scripts/seed.py full
```

## Testes

```bash
# API — suite completa sem LLM real
cd api && uv run pytest -m "not nightly"

# API — evals com LLM (requer ANTHROPIC_API_KEY)
cd api && uv run pytest -m nightly

# Web — unitários e de componente
pnpm --filter web test

# Web — E2E
pnpm --filter web test:e2e
```

## Estrutura

```
api/            API Python (FastAPI + Agno AgentOS)
  app/          código da aplicação
  alembic/      migrations do banco próprio
  fixtures/     respostas pré-gravadas para DEMO_REPLAY=true
  scripts/      seed (minimal|demo|full), export_openapi
  tests/        pytest: smoke + evals nightly
web/            painel Next.js (App Router)
  src/app/      rotas e Route Handlers (BFF)
  src/components/
  src/lib/      client gerado, hooks, utils
docs/adr/       Architecture Decision Records
DEMO.md         guia de demo local sem credencial de LLM
```

## Situação atual

- [x] Decisões de arquitetura registradas (9 ADRs)
- [x] Schema de configuração versionada e migrations
- [x] Factory de agente construído por request
- [x] Linter de prompt e estimativa de custo
- [x] Auth JWT RS256 com papéis e scopes (owner / editor / viewer)
- [x] Metering de consumo por período
- [x] CI com evals de confiabilidade (smoke + nightly)
- [x] Painel: login, sessão e proteção de rotas
- [x] Painel: lista e edição de agentes
- [x] Painel: seletor de modelo com capabilities condicionais
- [x] Painel: versões, diff visual e rollback
- [x] Painel: modo teste com chat integrado
- [x] Histórico de execuções por agente (runs, latência, erros)
- [x] Métricas por agente: p50/p95 de latência e taxa de erro
- [x] Painel Analytics global: volume, latência, custo e tokens — com filtro de período e intervalo de datas
- [x] Imagem Docker versionada publicada no GHCR
- [x] Demo com replay de inferência sem credencial de LLM (`DEMO_REPLAY=true`)
- [x] Seed completo para portfólio: 5 agentes + 500 runs históricos realistas

## Licença

Ver [`LICENSE`](LICENSE). O raciocínio de licenciamento está em [ADR-0007](docs/adr/0007-licenciamento.md).

---

Construído sobre [Agno](https://github.com/agno-agi/agno). Nenhum dado, prompt de produção ou identificação de cliente consta neste repositório.
