# Automata

[![CI](https://github.com/WellCod/automata/actions/workflows/ci.yml/badge.svg)](https://github.com/WellCod/automata/actions/workflows/ci.yml)
[![Publish](https://github.com/WellCod/automata/actions/workflows/publish.yml/badge.svg)](https://github.com/WellCod/automata/actions/workflows/publish.yml)

Plataforma para operar agentes de IA em produção. Com ela, quem não programa cria, versiona, testa e publica agentes, times multi-agente e workflows. Também liga bases de conhecimento (RAG), ferramentas via MCP e guardrails, roda suítes de teste por agente antes de publicar e acompanha execução, latência e custo de cada um.

O runtime é o [Agno](https://github.com/agno-agi/agno) (AgentOS). O Automata é a camada de produto em volta: configuração versionada em banco próprio, validação antes de publicar, rastreamento de cada execução, segurança e painel.

![Workflow com etapas em paralelo e condição](docs/img/workflow.png)

| | |
|---|---|
| **Backend** | Python 3.12 · FastAPI · Agno 3.1.8 · PostgreSQL 17 + pgvector · Redis · Alembic |
| **Frontend** | Next.js 16 · React 19 · TypeScript strict · Tailwind 4 · shadcn/ui · TanStack Query |
| **Qualidade** | mypy strict · ruff · ~460 testes pytest (testcontainers) · 131 testes Vitest · Playwright · evals |
| **Decisões** | 17 ADRs com contexto, alternativas descartadas e gatilho de reversão |

---

## Sumário

- [O problema](#o-problema)
- [O que a plataforma faz](#o-que-a-plataforma-faz)
- [Arquitetura](#arquitetura)
- [Como funciona por dentro](#como-funciona-por-dentro)
- [Segurança](#segurança)
- [Qualidade e testes](#qualidade-e-testes)
- [Decisões de arquitetura](#decisões-de-arquitetura)
- [Rodando local](#rodando-local)
- [Estrutura do repositório](#estrutura-do-repositório)

---

## O problema

Colocar um agente de IA em produção é simples. Operar quarenta, com equipes diferentes editando prompts, é outro problema:

- **Prompt sem histórico.** Alguém ajusta uma instrução às 18h, a qualidade cai e não há caminho de volta.
- **Troca de modelo quebra comportamento em silêncio.** Instruções acopladas a um provider degradam ao migrar de modelo sem gerar erro.
- **Custo opaco até a fatura chegar.** Sem estimativa antes de publicar, um prompt longo vezes o volume mensal estoura o orçamento.
- **Configuração e prompt divergem.** O prompt cita uma ferramenta que não está habilitada. Isso não falha no deploy, falha na conversa com o cliente.
- **Dado sensível e abuso.** CPF colado no chat vai para o provedor e para o log, e "ignore as instruções anteriores" funciona.

O Automata trata esses pontos como requisito de produto, não como disciplina de quem edita.

---

## O que a plataforma faz

### Agentes com versão, teste e rollback

Cada agente é uma configuração versionada: modelo, instruções em seções (persona, situação, tom, objetivo, limites), ferramentas, bases de conhecimento, guardrails e capabilities. Publicar cria uma versão imutável; rollback move um ponteiro. O modo teste roda a versão publicada ou o rascunho, sem publicar.

![Configuração de um agente com o modo teste ao lado](docs/img/agente.png)

Antes de salvar, a API recusa o que quebraria em produção:
- capability que o modelo não suporta (pensamento estendido em modelo sem thinking);
- tool de servidor MCP que não existe mais;
- base de conhecimento apagada;
- instrução acoplada a um provider.

Enquanto se edita, o painel mostra o **linter de prompt** e a **estimativa de custo** por mensagem e por volume mensal.

![Lista de agentes](docs/img/agentes.png)

### Times multi-agente

Um líder com modelo e instruções próprias coordena agentes publicados. Quatro modos, mapeados para o `TeamMode` do Agno:

| Modo | Como o líder trabalha |
|---|---|
| **Coordenar** | Divide a tarefa, delega a quem precisar e junta as respostas |
| **Rotear** | Escolhe um membro e devolve a resposta dele sem reescrever (handoff) |
| **Consultar todos** | A mesma tarefa vai a todos os membros, e o líder consolida |
| **Tarefas** | Monta uma lista de tarefas e acompanha até concluir |

A delegação é feita por tool call do próprio líder (`delegate_task_to_member`). A **descrição** de cada agente é o que o líder lê para decidir a quem passar o caso, por isso ela é obrigatória e aparece no painel como contrato. Cada membro segue a versão vigente ou fica fixado numa versão. O modo teste mostra o rastro: a quem o líder delegou e que tools o membro chamou.

![Editor de time](docs/img/time.png)

### Workflows por etapas

Quando o processo é conhecido e precisa ser repetível e auditável, um líder decidindo na hora não serve. O workflow é um fluxo fixo montado num editor visual sobre agentes e times publicados:

- **Etapa:** um agente ou time responde. Se falhar, para o fluxo ou segue, com até 3 tentativas.
- **Paralelo:** de 2 a 5 ramos recebem a mesma entrada ao mesmo tempo.
- **Condição:** regra sobre a mensagem do usuário ou a resposta anterior (contém, não contém, começa com, vazia), com então e senão.
- **Repetição:** limite de voltas e regra de parada ("até a revisão dizer *aprovado*").

O modo teste lê o stream do AgentOS e mostra cada etapa ao vivo: quem respondeu, o que respondeu, se a condição deu verdadeira, em que volta está a repetição e onde falhou. As execuções mostram o consumo somado de todas as etapas.

<p align="center"><img src="docs/img/workflow-teste.png" alt="Modo teste do workflow com progresso por etapa" width="420"></p>

### Bases de conhecimento (RAG)

Bases com PDF, DOCX, Markdown, texto, CSV, JSON ou páginas web, enviados por arrastar e soltar, URL ou texto colado. O painel mostra o estado de cada documento (processando, trechos indexados, motivo da falha). A **busca de teste** mostra exatamente os trechos que o agente receberia para uma pergunta, sem rodar o agente.

![Busca de teste numa base de conhecimento](docs/img/conhecimento.png)

Cada base escolhe como buscar: a busca simples, diversidade (MMR, para manuais longos e documentos repetidos), recência (para políticas que mudam) e, opcionalmente, HyDE, que busca com uma resposta hipotética quando a pergunta não usa as palavras do documento. A busca de teste mostra lado a lado o resultado com a estratégia e sem ela, e os tokens que o HyDE gastou.

### Guardrails por agente

Regras de entrada e saída versionadas junto com o agente. O bloqueio acontece antes da chamada ao modelo, então não gasta token.

- **Dados pessoais:** CPF e CNPJ com dígito verificador e cartão com Luhn, para que número de pedido não seja confundido com documento. Também e-mail e telefone. Cada tipo pode ser mascarado ou bloqueado.
- **Injeção de prompt:** detectada em português e inglês, sem diferenciar acento.
- **Outras regras:** tópicos proibidos, tamanho máximo e moderação opcional da OpenAI.
- **Na resposta:** dado pessoal ou termo proibido troca a resposta antes de ela sair.

Execuções barradas aparecem como **bloqueadas**, com a regra, separadas de falha no analytics.

<p align="center"><img src="docs/img/guardrails.png" alt="Guardrails de um agente" width="560"></p>

### Testes por agente antes de publicar

Cada agente e time tem uma suíte de casos: uma mensagem e o que precisa ser verdade na resposta. As checagens são três: texto (contém, não contém, começa com), tools que precisam ser chamadas (a busca na base certa, a tool MCP esperada) e um critério avaliado por um modelo juiz, binário ou nota com limiar. A suíte roda contra o rascunho ou a vigente, mostra o resultado caso a caso e compara as duas versões, apontando o que passou a falhar.

Com o **gate** ligado, publicar exige a suíte verde no rascunho atual. Editar o rascunho invalida o resultado. Os casos ficam fora da versão: um rascunho que muda o prompt não consegue afrouxar o próprio teste.

<p align="center"><img src="docs/img/testes.png" alt="Aba Testes de um agente com resultado por caso e comparação entre versões" width="600"></p>

A suíte também roda sem ninguém clicar. Um **agendamento** por agente roda a suíte na versão vigente e pega o que muda por fora do prompt: modelo do provedor, base reindexada, servidor MCP. A lista de agentes e times mostra o estado da suíte, e a execução agendada que perde um caso que passava aparece como regressão. Um **token de integração** pode rodar e ler a suíte de agentes escolhidos, para o CI de quem consome o agente decidir pelo `verdict`.

Caso novo não precisa nascer do zero. No histórico de execuções, **Virar caso de teste** abre o formulário preenchido com a mensagem, os turnos anteriores como contexto e as tools que o run chamou. Dados pessoais chegam mascarados, e o editor revisa antes de salvar.

### Ferramentas via MCP e confirmação humana

Catálogo de servidores MCP externos, com credenciais cifradas e teste de conexão que descobre as tools. Em cada agente, escolhe-se quais tools ele usa e quais **pedem confirmação**. Uma tool sensível pausa a execução até alguém aprovar ou rejeitar, no modo teste ou na página Aprovações, vendo nome e argumentos da ação.

O caminho inverso também existe: os próprios agentes e times ficam expostos via **MCP server mode** para Claude Desktop, Cursor e outros sistemas, com tokens de integração limitados aos agentes escolhidos e revogáveis na hora.

### Analytics e rastreamento

Conversas, taxa de falha, bloqueios, latência p50 e p95, tokens e custo, com gráficos diários e uso por agente. Cada execução abre como **árvore**, com time, agentes, chamadas de modelo e tools, e mostra duração, entrada, saída e erro de cada nó.

![Analytics](docs/img/analytics.png)

Tema claro e escuro, escolhido pelo usuário:

![Analytics no tema claro](docs/img/analytics-claro.png)

---

## Arquitetura

```mermaid
flowchart LR
    subgraph Browser
        UI[Painel Next.js]
    end
    subgraph web["web/ (Next.js, server-side)"]
        BFF["Route Handlers (BFF)<br/>cookie httpOnly → Bearer<br/>CSRF por Origin"]
    end
    subgraph api["api/ (FastAPI + AgentOS)"]
        R["Rotas próprias /api/v1<br/>configs, runs, métricas,<br/>bases, MCP, usuários"]
        OS["AgentOS (Agno)<br/>/agents /teams /workflows<br/>/mcp (server mode)"]
        F["Factories por request<br/>agente · time · workflow"]
        T["RunTracking<br/>agent_run · usage_event"]
    end
    PG[("PostgreSQL 17<br/>config versionada, runs,<br/>metering, pgvector")]
    RD[("Redis<br/>rate limit")]
    LLM["Provedores<br/>Anthropic · OpenAI"]
    MCP["Servidores MCP<br/>externos"]
    EMB["Embeddings<br/>Voyage · OpenAI"]

    UI --> BFF --> R & OS
    OS --> F --> T --> PG
    R --> PG
    R --> RD
    F --> LLM & MCP & EMB
```

O painel nunca fala direto com a API: todo acesso passa por Route Handlers server-side, e o token fica num cookie httpOnly. A API tem dois lados. As rotas próprias, em `/api/v1`, gerenciam configuração, execuções, métricas, bases, servidores MCP e usuários. As rotas do AgentOS executam agentes, times e workflows; o Automata não as modifica, só registra nelas o que foi publicado.

---

## Como funciona por dentro

### Configuração versionada e factory por request

`agent_config` guarda os ponteiros `current_version_id` e `draft_version_id`. `agent_config_version` guarda o payload em JSONB. Agente, time e workflow usam a mesma tabela, diferenciados por `kind`.

```text
rascunho ──publicar──▶ v3 (publicada, imutável) ◀── current_version_id
                       v2 (publicada)
                       v1 (publicada)            rollback = mover o ponteiro
```

- **Publicar nunca faz UPDATE.** Cria uma versão nova a partir do rascunho e move o ponteiro. Rollback só aceita versão publicada do mesmo config.
- **O payload tem `schema_version`.** Formatos antigos são convertidos na leitura, por um validator do pydantic, sem migração de dados.
- **O agente não é um objeto em código.** `AgentFactory`, `TeamFactory` e `WorkflowFactory` do Agno reconstroem tudo a cada request a partir da versão vigente: modelo, instruções, tools MCP, buscas nas bases e guardrails como `pre_hooks` e `post_hooks`. Com `version_id` no `factory_input`, a mesma factory roda um rascunho, que é como o modo teste funciona. A versão precisa pertencer ao config, senão um rascunho de B rodaria com o custo contado em A.
- **Publicar não exige restart.** O AgentOS lê listas mutáveis de agentes, times e workflows a cada request. Publicar registra a factory na hora, e outros workers sincronizam por um middleware com TTL de 5 s.

### Rastreamento e consumo

Hooks de pós-execução do Agno não rodam em erro nem em cancelamento. Por isso, o mixin `RunTracking` envolve `arun` e `acontinue_run`, nos modos coroutine e stream, e grava em `agent_run` (status, duração, erro, tools pendentes, regra de bloqueio) e em `usage_event` (tokens, custo, período) numa transação só.

- **Status:** `success`, `error`, `cancelled`, `paused` (aguardando confirmação humana) e `blocked` (guardrail).
- **Times:** só o run do time é gravado, porque o Agno já soma nele o consumo dos membros.
- **Workflows:** o `TrackedWorkflow` fixa o `run_id` antes de rodar e o publica numa `ContextVar`. Cada etapa grava esse id como `parent_run_id`, inclusive os ramos paralelos, que rodam em tasks que herdam o contexto. O consumo do workflow é a soma das etapas, e o analytics não conta nada duas vezes.

### Workflows

A árvore do payload (`step`, `parallel`, `condition`, `loop`) vira `Step`, `Parallel`, `Condition` e `Loop` do Agno, montados do zero a cada request. Três decisões saíram de comportamentos do Agno ([ADR-0014](docs/adr/0014-workflows-por-etapas.md)):

- **Uma instância nova por etapa.** Com a mesma instância, ramos paralelos compartilhariam estado e conexão MCP.
- **Etapa com erro levanta `StepFailed`.** No Agno, a etapa seguinte receberia a mensagem de erro como se fosse resposta. Com a exceção, `on_error` e `max_retries` passam a valer. Quando o fluxo para, o `TrackedWorkflow` converte a falha num run com status de erro, em vez do 500 que a rota devolveria.
- **Regras próprias em vez de CEL.** Sem o pacote `cel-python`, o Agno avalia toda expressão como `False` em silêncio. Além disso, expressão é linguagem de programação dentro de um painel para quem não programa. Depois de um paralelo, a regra lê a resposta do último ramo, não a frase-resumo que o Agno põe no lugar.

Limites validados na escrita: 3 níveis de aninhamento, 30 etapas, nomes únicos e o fluxo não termina num paralelo. Agente com tool de confirmação humana não entra em workflow, porque o fluxo não pausa no meio.

### RAG

```mermaid
flowchart LR
    D[PDF · DOCX · MD · CSV<br/>JSON · URL · texto] --> C["Chunking recursivo<br/>2000 caracteres, overlap de 10%"]
    C --> E["Embedder medido<br/>Voyage voyage-3.5 ou<br/>OpenAI text-embedding-3-small"]
    E --> V[("PgVector<br/>tabela kb_‹id› por base<br/>busca híbrida, português")]
    Q[Pergunta do usuário] --> A[Agente]
    A -- "tool buscar_‹slug›" --> V
    V -- "trechos + documento de origem" --> A
```

- **Pgvector no Postgres que já existe.** Cada base tem sua tabela vetorial, com dimensão fixada pelo embedder escolhido na criação, e busca híbrida (vetor + texto) configurada para português. Nada de serviço vetorial à parte ([ADR-0012](docs/adr/0012-bases-de-conhecimento.md)).
- **Ingestão em background.** O estado de cada documento fica em `knowledge_content`. O primeiro trecho é embedado antes do insert, para que chave inválida ou cota estourada vire mensagem de falha legível; depois do insert, os trechos são contados. Documento preso em "processando" por mais de 30 min vira falha no boot.
- **Uma tool por base.** O agente recebe `buscar_<slug>`, e a descrição da base diz quando usar. A tool devolve trechos com documento e fonte, e as instruções mandam citar o documento e tratar o trecho como **dado, não instrução**, uma defesa contra injeção vinda de documento.
- **Custo de embedding no metering.** `MeteredEmbedder` conta tokens de ingestão e de busca, com um cache curto para não pagar duas vezes pela mesma consulta.
- **Demo sem chave.** No modo replay, um embedder local determinístico indexa e busca por palavra em comum.

### Evals por agente

Os casos viram `Case`s do runner de suíte do próprio Agno (`agno.eval.suite`), que roda um por vez com timeout e checa tools esperadas (`ReliabilityEval`), critério do juiz (`AgentAsJudgeEval`) e um `Scorer` próprio para as regras de texto ([ADR-0015](docs/adr/0015-evals-por-agente.md)).

- **Mesmo agente de produção.** Cada caso ganha uma instância nova, montada pela mesma factory dos runs reais a partir da versão testada: mesmas tools, bases e guardrails. A execução é em background, e cada resultado é gravado assim que o caso termina.
- **Runs de teste não são conversas.** Uma `ContextVar` marca `agent_run.eval_run_id` e `usage_event.eval_run_id`. Esses runs ficam fora do histórico, das aprovações e das métricas; o custo continua no metering, separado como custo de testes.
- **Juiz com modelo nosso e medido.** Sem modelo explícito, o Agno cairia num modelo da OpenAI. O modelo do juiz é escolhido entre os que têm saída estruturada e embrulhado num medidor que soma os tokens dele no consumo da execução. No modo demo, o juiz aparece como "não avaliado" em vez de fingir aprovação.
- **Gate sem hash.** Cada rascunho salvo já é uma versão nova, então o resultado vale para aquele `version_id` e nenhum outro. Caso não avaliado não conta como aprovado, e rollback segue livre.

### MCP

- **Cliente de servidores externos.** Só streamable-http. Os headers de autenticação ficam cifrados com Fernet. Há proteção contra SSRF: só https, DNS resolvido e IP privado, loopback e link-local recusados, salvo hosts liberados por variável. A conexão é estrita: servidor fora do ar faz o run falhar com o motivo, em vez de o agente responder sem as tools ([ADR-0010](docs/adr/0010-servidores-mcp-externos.md)).
- **Confirmação humana.** Tools marcadas viram `requires_confirmation_tools` no Agno. O run pausado guarda as tools pendentes em `agent_run.pending_tools`, aparece em Aprovações e continua pela rota de continue do AgentOS.
- **Server mode.** O próprio AgentOS expõe os agentes por MCP, autenticado com JWT RS256. Tokens de integração têm `jti`, escopo por agente ou time, validade de até 90 dias e revogação imediata ([ADR-0009](docs/adr/0009-superficie-de-integracao.md)).

---

## Segurança

| Área | Implementação |
|---|---|
| **JWT RS256** | A API assina com a chave privada, que nunca sai dela. O AgentOS valida com a pública e com `user_isolation`. O token expira em 1 h e leva `jti`. |
| **BFF** | Cookie httpOnly e `sameSite=lax`, `secure` em produção. O proxy server-side converte o cookie em `Authorization: Bearer` e limpa a sessão no 401. Nenhum segredo vai para o bundle, e um teste no CI procura chaves no build. |
| **CSRF** | `Origin` conferido contra `Host` em todo método que não é seguro. |
| **Revogação** | Logout revoga o `jti`. Mudar papel, desativar ou trocar senha corta na hora as sessões da pessoa. |
| **Papéis e scopes** | `owner`, `editor`, `viewer`. Toda rota, própria ou do AgentOS, exige scope. |
| **Rate limit** | Login limitado por e-mail e por IP no Redis. `X-Forwarded-For` só vale vindo de proxy listado em `TRUSTED_PROXIES`. |
| **Superfície** | Login com e-mail inexistente também roda argon2, para a latência não revelar contas. `/docs` e `/openapi.json` só em desenvolvimento. |
| **Headers** | HSTS, CSP com `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy`. |

---

## Qualidade e testes

| Camada | Ferramenta | Cobertura |
|---|---|---|
| API | pytest + testcontainers | ~460 testes contra Postgres com pgvector real, sem mock de banco. Gate de cobertura de 70%. |
| Tipos | mypy strict + plugin pydantic · ruff | Rodam em todo PR. |
| Web | Vitest + Testing Library | 131 testes de componente e de lógica, inclusive o redutor de eventos do workflow e a suíte de testes. |
| E2E | Playwright | Login → editar agente → publicar → rollback. |
| Contrato | openapi-typescript | Os tipos do painel são gerados do OpenAPI da API, nunca escritos à mão. |

**Evals** medem o comportamento que importa, não só se o código roda:

| Eval | O que mede | Quando roda |
|---|---|---|
| Guardrails | 30 mensagens com a regra que deveria barrar cada uma ou nenhuma. Um terço são casos legítimos (número de pedido, "política de reembolso") que precisam passar. | Todo PR |
| Workflows | Regras sobre respostas reais de triagem, inclusive os limites documentados (negação, flexão), condição depois de paralelo e estrutura aceita ou recusada. | Todo PR |
| Suíte de testes | Scorer de texto sobre respostas reais, montagem do `Case` do Agno (juiz só com modelo, nunca no modo demo), tradução do resultado do runner, veredito do gate (não avaliado trava) e comparação entre execuções. | Todo PR |
| Evals contínuos | Validação do agendamento (cron, fuso, intervalo mínimo de 1 hora), próximo horário no fuso certo, escopo por recurso dos tokens de integração, `verdict` que o pipeline lê e montagem da sugestão de caso (máscara, tools com erro fora). | Todo PR |
| Recuperação | O documento certo volta entre os 3 primeiros trechos. A versão literal roda em todo PR; a semântica, com Voyage, roda à noite e aceita recall@3 de 80%. | PR e noturna |
| Confiabilidade | Tool calls com LLM real. | Noturna |

**CI** (GitHub Actions): filtro por caminho, jobs de API, web e e2e, montagem das imagens de produção da API e do painel e um gate que falha se qualquer um falhar. Tag `v*` publica as imagens no GHCR e anexa o `openapi.json` na release.

---

## Decisões de arquitetura

Cada decisão relevante está em [`docs/adr/`](docs/adr/), com contexto, alternativas descartadas e o gatilho concreto que faria reverter.

| ADR | Decisão |
|---|---|
| [0001](docs/adr/0001-monorepo.md) | Monorepo sem ferramenta de monorepo: `uv` e `pnpm` bastam |
| [0002](docs/adr/0002-config-em-banco-proprio.md) | Configuração em banco próprio, não no editor do framework |
| [0003](docs/adr/0003-single-tenant.md) | Uma instância por cliente, e a assimetria que torna difícil desfazer |
| [0004](docs/adr/0004-painel-proprio.md) | Painel próprio; o Control Plane do Agno só como ferramenta interna |
| [0005](docs/adr/0005-auth-jwt-proprio.md) | JWT RS256 próprio; a chave de assinatura nunca sai do servidor |
| [0006](docs/adr/0006-instructions-agnosticas-de-provider.md) | Instruções sem termos de provider, a regra que sustenta trocar de modelo |
| [0007](docs/adr/0007-licenciamento.md) | Código aberto sob AGPL-3.0 com licença comercial paralela |
| [0008](docs/adr/0008-demo-com-respostas-gravadas.md) | Demo pública com respostas gravadas, sem chave de LLM |
| [0009](docs/adr/0009-superficie-de-integracao.md) | REST e MCP server mode como superfície de integração |
| [0010](docs/adr/0010-servidores-mcp-externos.md) | Servidores MCP externos: segredo cifrado, só HTTP, falha visível |
| [0011](docs/adr/0011-times-versionados.md) | Times na mesma tabela de configs, membros seguindo a versão vigente |
| [0012](docs/adr/0012-bases-de-conhecimento.md) | RAG com pgvector no Postgres existente e embeddings da Voyage |
| [0013](docs/adr/0013-guardrails-por-agente.md) | Guardrails versionados com o agente, bloqueio sem custo de modelo |
| [0014](docs/adr/0014-workflows-por-etapas.md) | Workflows por etapas com regras sem CEL e etapa com erro que para o fluxo |
| [0015](docs/adr/0015-evals-por-agente.md) | Evals por agente no painel: casos fora da versão, runner de suíte do Agno e gate de publicação |
| [0016](docs/adr/0016-evals-continuos.md) | Evals contínuos: suíte por token de integração, agendamento próprio e casos de conversas reais |
| [0017](docs/adr/0017-estrategia-de-recuperacao.md) | Estratégia de recuperação por base: reranker do Agno (MMR, recência) e HyDE com modelo medido (proposto, Fase 18) |

O histórico de fases, com os problemas encontrados em auditoria e o critério de aceite de cada uma, está em [`docs/roadmap.md`](docs/roadmap.md).

---

## Rodando local

**Pré-requisitos:** Docker Desktop, Node.js 22+, pnpm, Python 3.12+, `uv` e `openssl`.

```bash
git clone https://github.com/WellCod/automata.git
cd automata
bash scripts/bootstrap.sh   # gera chaves RSA, cria .env, instala dependências e sobe o banco
```

### Demo sem chave de LLM

Com `DEMO_REPLAY=true`, o modelo é trocado por respostas gravadas em `api/fixtures/` e as bases usam um embedder local. Edição, versões, modo teste, workflows e analytics funcionam sem chave nenhuma.

```bash
# API em modo replay (--build -V recria imagem e venv se as dependências mudaram)
DEMO_REPLAY=true docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build -V

# Seed: owner, 5 agentes, base de conhecimento, workflow, suíte de testes e 500 execuções em 90 dias
read -rsp "Senha do owner: " SEED_OWNER_PASSWORD; echo
docker exec \
  -e SEED_OWNER_EMAIL="admin@exemplo.com" \
  -e SEED_OWNER_PASSWORD="$SEED_OWNER_PASSWORD" \
  automata-api-1 bash -c "cd /app && .venv/bin/python scripts/seed.py full"

# Painel
pnpm --filter web dev   # http://localhost:3000
```

Guia completo, com o que o seed cria e como as fixtures funcionam, em [`DEMO.md`](DEMO.md).

### Desenvolvimento

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up   # API em :8000, migrations no boot
pnpm --filter web dev                                                 # painel em :3000
```

A porta 8000 só é publicada pelo override de dev. Em produção, a API fica na rede do compose e o painel fala com ela por `http://api:8000`. Depois de um `git pull` que mexa em `api/uv.lock`, recrie a API com `--build -V`. Sem o `-V`, o volume anônimo do venv mantém as dependências antigas.

### Testes

```bash
cd api && uv run pytest -m "not nightly"   # API, com testcontainers
cd api && uv run pytest -m nightly         # evals com LLM real (ANTHROPIC_API_KEY)
pnpm --filter web test                     # Vitest
pnpm --filter web test:e2e                 # Playwright
```

---

## Estrutura do repositório

```
api/
  app/
    agents/       factories, rastreamento, workflows, modelos, replay
    evals/        runner da suíte, juiz medido e gate de publicação
    guardrails/   regras de entrada e saída
    knowledge/    embedders, ingestão, tools de busca
    mcp/          cliente MCP, proteção de saída (SSRF)
    routers/      rotas próprias /api/v1
    services/     regras de negócio e validação na escrita
  alembic/        28 migrations
  fixtures/       respostas gravadas do modo replay
  tests/          pytest, integração e evals
web/
  src/app/        páginas e Route Handlers (BFF)
  src/components/ editor de workflow, suíte de testes, modo teste, painéis
  src/lib/        client gerado do OpenAPI, SSE, progresso do workflow
  e2e/            Playwright
docs/
  adr/            15 Architecture Decision Records
  roadmap.md      fases, auditorias e critérios de aceite
DESIGN.md         sistema visual do painel
DEMO.md           demo local sem chave de LLM
```

---

## Licença

Ver [`LICENSE`](LICENSE). Justificativa em [ADR-0007](docs/adr/0007-licenciamento.md).

Construído sobre o [Agno](https://github.com/agno-agi/agno). Nenhum dado de produção, prompt real ou identificação de cliente consta neste repositório; os prints usam o seed de demonstração.
