# Automata

Plataforma de gestão de agentes de IA em produção: catálogo, edição versionada, troca de modelo sem reescrita de prompt e rastreio de custo por agente.

> **Status: em construção.** Este repositório está na fase de fundação — decisões de arquitetura registradas, código em implementação. O que já existe está listado em [Situação atual](#situação-atual). Nada aqui descreve funcionalidade que ainda não roda.

---

## O problema

Colocar um agente de IA em produção é fácil. Operar quarenta é outro problema.

O que aparece quando a quantidade cresce:

**Prompt em produção não tem histórico.** Alguém ajusta uma instrução às 18h de sexta, a qualidade cai, e não existe caminho de volta. O prompt não está em código, está num campo de texto que foi sobrescrito.

**Trocar de modelo é reescrever prompt.** Instruções que dizem "responda em JSON sem markdown" ou que mencionam blocos de raciocínio estão acopladas a um provider específico. Trocar o modelo quebra o comportamento de forma silenciosa — a saída degrada, mas não dá erro.

**O custo é opaco até a fatura chegar.** Sem estimativa antes de publicar, não há como saber se um prompt de três mil tokens vezes o volume mensal cabe no contrato.

**A configuração e o prompt divergem.** O prompt menciona uma função que não está habilitada no agente. Isso não falha no deploy — falha na conversa com o usuário final, dias depois.

Automata trata esses quatro problemas como requisito de produto, não como disciplina de quem edita.

## Como resolve

**Versionamento imutável.** Publicar cria uma versão nova e move um ponteiro. Versão publicada nunca sofre alteração. Rollback é mover o ponteiro de volta — operação de um clique, não de um deploy.

**Modelo como campo.** O agente referencia um identificador de modelo, resolvido em tempo de execução. As instruções são validadas contra uma lista de termos acoplados a provider, e o build falha se alguma passar. A troca de modelo continua sendo um campo porque existe um teste garantindo isso.

**Capabilities validadas na escrita.** Se a configuração pede raciocínio estendido e o modelo escolhido não suporta, a validação recusa no momento de salvar — não em produção. O painel desabilita a opção e explica o motivo.

**Linter de prompt.** Função citada nas instruções e não habilitada no agente vira aviso na própria tela de edição, com ação para habilitar.

**Estimativa antes de publicar.** Tokens estimados, custo por mensagem e projeção por volume, visíveis enquanto se edita.

## Decisões de arquitetura

A parte substantiva deste repositório está em [`docs/adr/`](docs/adr/). Cada registro tem contexto, alternativas descartadas com o motivo específico, consequências — incluindo o que ficou pior — e o gatilho concreto que faria reverter.

Os mais relevantes para entender o desenho:

- [ADR-0003 — Deploy single-tenant](docs/adr/0003-single-tenant.md): por que uma instância por cliente, e a assimetria que torna essa a migração difícil de desfazer
- [ADR-0002 — Config em banco próprio](docs/adr/0002-config-em-banco-proprio.md): por que não usar o editor visual do framework como fonte da verdade
- [ADR-0006 — Instructions agnósticas de provider](docs/adr/0006-instructions-agnosticas-de-provider.md): a regra que sustenta a promessa de trocar modelo
- [ADR-0005 — Auth](docs/adr/0005-auth-jwt-proprio.md): por que a chave de assinatura nunca chega ao browser

## Arquitetura

Três camadas, com fronteira clara de quem escreve o quê:

```
┌─────────────────────────────────────────────┐
│  web/  — painel                             │
│  lista · edição versionada · modo teste     │
└────────────────────┬────────────────────────┘
                     │  BFF: Route Handlers do Next
                     │  (chave de assinatura fica no servidor)
┌────────────────────┴────────────────────────┐
│  api/  — FastAPI sobre Agno AgentOS         │
│  config versionada · factory · linter       │
│  metering · migrations próprias             │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────┴────────────────────────┐
│  Agno SDK + AgentOS                         │
│  REST · JWT com scopes · traces · sessions  │
└─────────────────────────────────────────────┘
```

O agente não é um objeto estático em código. Ele é construído por request a partir da versão vigente da configuração, o que permite editar comportamento sem redeploy e rodar uma versão específica em modo teste.

## Stack

| Camada | Escolha | Motivo |
|---|---|---|
| Runtime de agente | Agno (AgentOS) | FastAPI pronto, JWT com scopes por endpoint, traces e sessions persistidos |
| API | Python 3.12, `uv` | Lockfile e resolução rápida |
| Banco | Postgres, Alembic | Migrations próprias, isoladas das tabelas do framework |
| Painel | Next.js, TypeScript, Tailwind, shadcn/ui | Mesma stack do `agent-ui`, que é forkado para a superfície de chat |
| Formulários | `react-hook-form` + `zod` | A tela de edição tem habilitação condicional; schema declarativo é requisito, não preferência |
| Testes | `pytest`, Vitest, Playwright | Mais os evals do próprio Agno para confiabilidade de tool call |

Monorepo sem ferramenta de monorepo: são duas aplicações isoladas em linguagens diferentes, e `uv` com `pnpm` bastam. Justificativa em [ADR-0001](docs/adr/0001-monorepo.md).

## Situação atual

- [x] Decisões de arquitetura registradas
- [ ] Fundação da API e schema de configuração versionada
- [ ] Factory de construção de agente por request
- [ ] Linter de prompt
- [ ] Painel: lista e edição
- [ ] Fork do chat para modo teste
- [ ] CI com evals de confiabilidade
- [ ] Demo pública

## Rodando local

```bash
git clone https://github.com/WellCod/automata.git
cd automata
cp .env.example .env    # preencha as chaves
docker compose up
```

Pré-requisitos: Docker, `uv` e `pnpm`.

## Estrutura

```
api/        API em Python sobre o Agno
web/        painel em Next.js
docs/adr/   decisões de arquitetura
docs/prompts/  scaffolding usado para gerar os projetos
```

## Licença

Ver [`LICENSE`](LICENSE). A intenção de licenciamento e o raciocínio por trás dela estão em [ADR-0007](docs/adr/0007-licenciamento.md), com status de proposta.

---

Construído sobre [Agno](https://github.com/agno-agi/agno). Nenhum dado, prompt de produção ou identificação de cliente consta neste repositório.