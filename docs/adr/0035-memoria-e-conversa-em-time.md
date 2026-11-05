# ADR-0035 — Memória do usuário no time e modelo próprio para o resumo da compactação

**Status:** Aceito
**Data:** 2026-11-04

## Contexto

A memória do usuário (ADR-0025) só vale no agente: um time com a opção dá erro na escrita. Um time de atendimento, que é o caso mais comum de conversa longa com o mesmo cliente, esquece o cliente a cada sessão.

A compactação (ADR-0019) usa o modelo do próprio agente para o resumo. Um agente em modelo grande paga o preço dele para resumir conversa, o que um modelo pequeno faz bem. O ADR-0019 deixou para depois o modelo próprio para o resumo e a compactação no líder do time.

Verificado no Agno 3.1.8 instalado:

- O `Team` aceita `memory_manager`, `update_memory_on_run` e `add_memories_to_context`, como o `Agent`. No fim do run, o time grava a memória com `team_id` igual ao id do time e `agent_id` vazio (`team/_managers.py`).
- O `PostgresDb.get_user_memories` filtra por `agent_id` ou por `team_id`.
- **O `Team` não tem `compaction`** (nenhuma ocorrência em `team/team.py`). Não há como compactar a conversa do líder sem reescrever o histórico do time por fora do Agno.
- A `Compaction` aceita `model` para o resumo (`compaction/compaction.py`). Sem `model`, usa o do agente.
- O consumo do resumo entra em `RunMetrics.details["compaction_model"]` com o id do modelo que resumiu. O `pricing.run_cost` precifica cada entrada pelo próprio id (ADR-0027).

## Decisão

**Memória do usuário no time.** O payload do time aceita a seção `memory` do ADR-0025: `enabled`, `instructions` e `retention_days`. O líder grava e lê as memórias do usuário, como o agente faz. A memória é do dono, que pode ser um agente ou um time:

- O manager lê pelo par usuário e dono: `agent_id` para agente e `team_id` para time. Um time não vê as memórias que os agentes guardaram, e um agente não vê as do time.
- A máscara de dados pessoais, com os padrões próprios (ADR-0032), procura os padrões pelo dono da memória gravada.
- A retenção de hora em hora, as rotas `/configs/{id}/memories` e `/me/memories` passam a tratar os dois tipos de dono. A exclusão do titular (ADR-0032) já apaga por usuário.
- Os membros do time não ganham memória própria dentro do time. A memória é do time, como o histórico da conversa.
- Run sem usuário e run da suíte seguem sem memória.

**Modelo próprio para o resumo.** `conversation.summary_model`, vazio por padrão, escolhido entre os modelos da matriz. Ele vira o `Compaction(model=...)`, sem extended thinking e com o retry da versão (ADR-0027). O custo do resumo sai pelo id desse modelo no custo do run e no orçamento.

**A compactação no líder do time não entra.** O `Team` do Agno 3.1.8 não tem compactação, e fazer por fora exigiria reescrever o histórico que o Agno manda ao modelo. Fica registrado até o Agno trazer o recurso. Enquanto isso, o time leva os últimos 5 turnos (`HISTORY_RUNS`).

## Alternativas descartadas

- **Memória por membro dentro do time.** Cada membro veria só o que ele guardou, e o líder, que fala com o cliente, ficaria sem a memória. A memória segue quem conversa.
- **Compartilhar memória entre agente e time do mesmo produto.** Vazaria entre configurações diferentes, que é o problema que o ADR-0025 resolveu.

## Consequências

- As memórias antigas de agente seguem como estão. As de time começam a partir da fase.
- O resumo num modelo mais barato pode perder nuances da conversa. A escolha fica com quem configura e aparece na tela da compactação.
