# ADR-0002 — Config de agente em banco próprio, não no AgentOS Studio

**Status:** Aceito
**Data:** 2026-08-05

## Contexto

O núcleo do produto é uma tela de edição de agente: modelo, instructions decompostas em seções, tools, flags de capability, tags, categoria, estimativa de custo e versionamento.

O Agno oferece o AgentOS Studio, que cobre parte disso — editor visual com modelo, tools, instructions, schemas de I/O, memória e knowledge, mais ciclo de rascunho, publicação e versionamento. Versões publicadas são imutáveis e um ponteiro define qual a API serve. Studio exige um `Registry` e um banco passados ao `AgentOS`.

## Decisão

Tabelas próprias de configuração, e o `Agent` construído a partir delas via `AgentFactory` por request. Studio não entra no produto.

## Alternativas descartadas

**Usar Studio como store de configuração.** Dos campos da tela pretendida, vários não existem no schema do Agno: tipo de canal, voz, modelo de transcrição, categoria de produto, tags, estimativa de custo. Eles virariam blob de metadata — e aí perde-se a validação que era o motivo de usar o schema dele, ganhando acoplamento à versão do Agno.

O motivo terminal, porém, é de produto: o Studio vive no Control Plane hospedado. Não é possível colocar um SaaS de terceiro no fluxo do cliente final. Ver ADR-0004.

**CRUD próprio sem versionamento.** A tela pressupõe histórico e rollback. Sem isso, prompt quebrado em produção não tem caminho de volta.

## Consequências

- Duas tabelas: `agent_config` (identidade estável, ponteiros para versão atual e rascunho) e `agent_config_version` (snapshot imutável em JSONB, validado por modelo Pydantic versionado).
- Publicar nunca faz `UPDATE` em versão publicada: cria linha e move o ponteiro. Rollback é só mover o ponteiro.
- O payload JSONB guarda a própria versão de schema, para permitir migração de formato depois.
- Migrations próprias via Alembic. O Agno gerencia as tabelas dele; o `env.py` precisa de `include_object` filtrando o que não é nosso, senão o autogenerate emite `DROP` nas tabelas do Agno. Coberto por teste que afirma migration vazia.
- Perdemos o editor visual pronto. A tela é código nosso.
- Ganhamos campos que o Agno não modela e liberdade de evoluir sem esperar release dele.

## O que me faria reverter

Se o Agno passar a expor o Studio de forma auto-hospedável e white-label, ou se o schema de componentes dele passar a aceitar metadata arbitrária com validação. Nesse caso, migrar valeria a pena para eliminar código de CRUD nosso.

Sinal de alerta na direção oposta: se a nossa tabela de config começar a divergir tanto do modelo do Agno que a factory fique cheia de tradução condicional, é sinal de que estamos reimplementando o framework e vale reavaliar a dependência inteira.
