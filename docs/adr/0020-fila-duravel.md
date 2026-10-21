# ADR-0020 — Fila durável do Agno para runs em background, no Postgres da instância, com Redis opcional

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-10-21

## Contexto

Sistemas consumidores podem chamar `POST /agents/{id}/runs` (e os de times e workflows) com `background=true`. A API aceita na hora, responde `PENDING` e o cliente consulta o run depois. Isso serve a integrações que não podem segurar uma conexão aberta, como webhooks de CRM e filas de atendimento.

Com a configuração atual, um run em background é uma task em memória do processo:

- **Reinício perde o run.** Um deploy ou um crash no meio da execução deixa o run `PENDING` ou `RUNNING` para sempre, e o cliente consulta um resultado que nunca chega.
- **Cancelar ou acompanhar só funciona na réplica que aceitou.** Com duas réplicas atrás de um balanceador, o pedido de cancelamento cai na outra e não acha a task.

Verificado no Agno 3.1.8 instalado e no código atual:

- `AgentOS(queue=QueueConfig(...))`. Com `durable=True`, aceitar um run vira uma linha commitada numa tabela de fila no banco do AgentOS, sem infraestrutura nova. Um worker por réplica reivindica as linhas, com heartbeat. Run de réplica que morreu é reivindicado de novo depois de `lock_grace_seconds`.
- `max_attempts` é 1 por padrão: run interrompido falha de forma visível e nunca roda de novo em silêncio. Isso importa para agente que chama tool com efeito colateral.
- `timeout_seconds` (padrão 3.600) limita cada execução, e `retention_seconds` (padrão 24 h) limpa a fila. Com `max_queue_depth`, a API responde 429 além de mil pendentes.
- `redis`, com uma URL, liga o cancelamento e o stream de eventos entre réplicas. Sem ele, o run é durável, mas o stream ao vivo é local da réplica.
- O worker resolve `AgentFactory`, `TeamFactory` e `WorkflowFactory` pelo registro do AgentOS. **Conferido com o nosso factory dinâmico:** um run em background passou pela fila durável, terminou `COMPLETED` com a resposta e ficou gravado em `agent_run` pelo `TrackedAgent`.
- O worker sobe no lifespan do AgentOS, que só passou a rodar com o #158. Antes dele, o app externo montava o AgentOS sem entrar no lifespan.
- O Redis já faz parte da stack (rate limiting, Fase 7) e fica configurado por `REDIS_URL`.

## Decisão

**Fila durável ligada por padrão, no Postgres da instância.** O `AgentOS` recebe:

- `QueueConfig(durable=True, max_attempts=1, timeout_seconds=900)`;
- `redis=REDIS_URL`, quando definido;
- o resto com os padrões do Agno.

Um run aceito sobrevive a deploy e a crash: outra réplica, ou a mesma depois do restart, termina ou marca a falha. A tabela fica no banco do AgentOS, sem serviço novo.

**Uma tentativa só.** Um agente pode ter chamado uma tool que envia e-mail ou cria pedido antes de cair. Rodar de novo sozinho repetiria o efeito. Run interrompido falha com o motivo, e o cliente decide se reenvia.

**15 minutos de limite por execução.** O padrão do Agno é uma hora. Um run de agente que passa de 15 minutos é quase sempre tool travada ou laço de delegação, e segurar o slot do worker por uma hora esconde o problema.

**Redis quando existir.** Com `REDIS_URL`, cancelar e acompanhar o stream funcionam de qualquer réplica. Sem ele, que é o caso de dev e de instância de uma réplica só, a fila segue durável.

**Interruptor por variável.** Com `BACKGROUND_QUEUE_DURABLE=false`, a API volta às tasks em memória, para diagnóstico ou para quem roda uma réplica descartável. O painel não muda: o modo teste usa stream, não background.

## Alternativas descartadas

- **Worker separado, com Celery ou RQ.** É mais um serviço para operar, e os runs teriam de sair do AgentOS, que é quem monta o agente pelo factory, aplica guardrails e grava a sessão. A fila do Agno roda o mesmo caminho do run síncrono.
- **Tabela de fila no Redis.** O Agno aceita um `db` próprio para a fila, mas o Redis da stack é cache e coordenação, sem persistência garantida. O Postgres já é o registro da instância e tem backup.
- **Mais tentativas com backoff.** Serviria a run idempotente, mas a API não sabe se as tools do agente são idempotentes. Fica 1, e quem precisar reenvia.
- **Manter as tasks em memória.** Com uma réplica e pouco tráfego, funciona até o primeiro deploy no meio de um run. É o padrão que perde dado em silêncio.

## Consequências

- Run em background aceito não se perde em deploy. O cliente vê `COMPLETED` ou uma falha com motivo, nunca `PENDING` para sempre.
- O worker consulta a tabela da fila a cada segundo quando ocioso. É uma carga pequena no Postgres, que o `poll_interval` do Agno controla.
- Mais de mil runs pendentes recebem 429. Quem integra precisa tratar isso como tratamos o rate limit.
- Na mudança de configuração da fila (prazos, tentativas), todas as réplicas precisam do mesmo valor, como avisa o Agno. Os valores ficam fixos no código, não por variável, para não divergir num rolling deploy.
- Depende do lifespan do AgentOS rodando (#158).

## O que me faria reverter

- Carga de polling da fila que pese no Postgres de uma instância grande. Nesse caso, a fila vai para um banco próprio pelo `QueueConfig.db`.
- Clientes que precisem de retry automático. Nesse caso, entra `max_attempts` maior por agente, marcado como idempotente no payload.
