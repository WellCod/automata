# ADR-0031 — Teto de custo por run e orçamento por quem chama

**Status:** Aceito
**Data:** 2026-11-04

## Contexto

O orçamento do ADR-0021 é mensal e por agente, checado antes do run. Ficam dois buracos:

- **Um run sozinho passa do orçamento.** Com tools em laço, modelo reserva, compressão (ADR-0029) e classificador no exame de tool (ADR-0030), um run pode custar muitas vezes uma resposta comum. O limite de chamadas de tool (ADR-0027) conta chamadas, não dinheiro. A auditoria da Fase 33 apontou o caso.
- **Não há teto por quem chama.** Um token de integração com um bug no cliente, ou um usuário do painel testando em laço, gasta o orçamento do agente e deixa os outros sem atendimento. O consumo já é gravado por `user_id`, e as chamadas de integração entram como `integration:<id>`, mas nada limita esse gasto.

Verificado no Agno 3.1.8 instalado:

- O gancho de tool recebe `run_context.messages`, a lista viva de mensagens do run (`run/base.py:39`). Cada mensagem do assistente traz `metrics` com tokens de entrada e saída.
- `StopAgentRun` (`exceptions.py:80`), levantado de dentro de uma tool ou de um gancho, chega ao laço do modelo como `AgentRunException` com `stop_execution`. O laço termina depois daquela tool, sem nova chamada ao modelo e sem erro (`models/base.py:2259-2265`).
- Sem tool não há segunda chamada ao modelo: o custo de um run assim já é limitado pelo `max_tokens` do provedor.

## Decisão

**Teto por run.** A seção `run` do payload (ADR-0027) ganha `max_cost_usd`, de 0,01 a 100, vazio por padrão. Um gancho de tool próprio roda antes de cada tool:

- soma os tokens das mensagens do assistente no `run_context.messages`;
- precifica pela tabela do modelo do agente (`pricing`, ADR-0021);
- ao passar do teto, não roda a tool e levanta `StopAgentRun`.

O Agno não chama o modelo de novo depois do `StopAgentRun`, e a resposta do run sairia vazia. O tracking põe no lugar uma mensagem fixa: a conversa chegou ao limite de custo por resposta. No stream, ela sai como evento de conteúdo no fim.

O run termina como sucesso, com `agent_run.stop_reason = "run_cost_limit"` (migration 0040), e não conta na taxa de erro. Vale no agente e no líder do time.

**Orçamento por quem chama.** Uma tabela `caller_budget` (migration 0041) guarda, por `subject`:

- o `subject` é o id do usuário do painel ou `integration:<id>` do token;
- o limite mensal em dólares;
- o percentual de aviso (padrão 80%);
- o bloqueio, ligado ou desligado.

Só o owner gerencia (scope `budgets:admin`). Um pre-hook, antes das regras de guardrail como o do ADR-0021, soma o gasto do mês daquele `user_id` em todos os agentes, com o mesmo cache curto. Com o bloqueio ligado e o limite estourado, barra o run como `budget_exceeded` com `scope: caller`. O aviso e o estouro saem pelos destinos de alerta da instância (ADR-0021) como `caller_budget.warning` e `caller_budget.exceeded`. A linha do orçamento guarda o último período avisado, para mandar cada aviso uma vez por mês.

## Alternativas descartadas

- **Parar o run no meio de uma chamada ao modelo.** O Agno não expõe gancho entre a resposta do modelo e a próxima chamada fora das tools. Cancelar o run pelo `cancel_run` descartaria a resposta parcial e o marcaria como cancelado.
- **Teto por run contando o custo informado pelo provedor.** Anthropic e OpenAI não devolvem custo, só tokens (ADR-0021), então a tabela de preços é a fonte nos dois casos.
- **Orçamento por quem chama em cada agente.** Daria uma linha por par usuário e agente. O que o owner quer limitar é o gasto daquele token ou usuário na instância.

## Consequências

- O teto por run é aproximado. Ele soma só as chamadas ao modelo do próprio run, com o preço do modelo do agente. Ficam fora o modelo reserva com preço diferente, a compressão, o classificador, o HyDE e os runs dos membros de um time. Tudo isso entra no orçamento mensal, que lê o `usage_event`.
- Um run pode passar do teto pelo custo de uma chamada ao modelo, porque a checagem é entre uma chamada e a próxima tool.
- Os runs da suíte de testes contam no orçamento de quem disparou a suíte, como já contam no consumo.
