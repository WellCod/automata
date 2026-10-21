# ADR-0021 — Custo calculado pela tabela de preços, orçamento mensal por config e destinos de aviso da instância

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-10-21

## Contexto

O analytics mostra custo por execução, por agente e por dia, mas nada impede um agente de gastar além do previsto. Um laço de tool, um HyDE ligado numa base muito consultada ou uma suíte agendada com juiz caro só aparecem na fatura do provedor.

Ao levantar a fase, apareceu um problema anterior: **o custo vem vazio com provedor real.**

- O `RunTracking` grava `usage_event.cost` a partir de `metrics.cost` do Agno.
- O Agno só preenche `cost` quando o provedor informa o valor na resposta, o que acontece com roteadores como o OpenRouter. A Anthropic e a OpenAI devolvem tokens, não custo.
- Os números que aparecem hoje vêm do seed da demo e do modelo de replay. Com chave real, custo, estimativa e qualquer orçamento em dólar ficariam vazios.

Também não há aviso de nada além da suíte agendada (ADR-0018): nem orçamento perto do limite, nem pico de erro. O ADR-0018 previu, no gatilho de reversão, um cadastro de destinos de aviso por instância quando aparecessem outros eventos.

No código atual:

- `BlockLog` e as regras de guardrail gravam `agent_run.blocked_by` e mantêm o run como `blocked`, separado de erro no analytics, sem chamar o modelo (ADR-0013).
- `app/evals/webhook.py` já faz entrega assinada, com filtro de saída, URL e segredo cifrados e até 3 tentativas.
- O poller das suítes agendadas roda a cada minuto no lifespan da API.

## Decisão

**Preço por modelo na matriz e custo calculado quando o provedor não informa.** A matriz de modelos ganha preço de entrada e de saída, em dólar por milhão de tokens. Quando o run não traz `metrics.cost`, o tracking calcula pelos tokens. O mesmo vale para o juiz da suíte e para o HyDE. O preço é de referência, a lista pública do provedor na data do ADR. `MODEL_PRICES` (JSON por variável) sobrescreve modelo a modelo, para contrato com desconto ou preço que mudou. O painel chama o valor de **custo estimado**.

**Orçamento mensal por config, fora da versão.** O `agent_config` ganha:

- `budget_monthly_usd`, vazio = sem orçamento;
- `budget_alert_percent`, padrão 80;
- `budget_hard_stop`, desligado por padrão.

Como o gate da suíte (ADR-0015), o orçamento é operação, não comportamento do agente: mudar o limite não pede nova versão.

- O gasto do mês é a soma dos `usage_event` do config no período corrente, incluindo testes e HyDE, porque é tudo gasto real.
- **Bloqueio ao estourar, se ligado.** A factory põe um hook antes dos guardrails que consulta o gasto do mês, com cache de 30 s. Estourado, o run é barrado como `blocked`, com `blocked_by: budget_exceeded`, e a mensagem diz que o orçamento do mês acabou. Não chama o modelo e não conta como erro.
- A checagem é antes do run, então um run longo pode passar um pouco do limite. O bloqueio vale do run seguinte em diante.

**Destinos de aviso da instância.** Um cadastro `alert_destination` com nome, URL e segredo cifrados e os eventos que cada destino recebe:

- `budget.warning` e `budget.exceeded`: uma vez por config e por mês em cada nível.
- `errors.spike`: taxa de erro de 50% ou mais em pelo menos 5 runs nos últimos 15 minutos, conferida pelo poller a cada minuto, no máximo um aviso por config por hora.
- `suite.regressed`, `suite.failing` e `suite.recovered`: os mesmos eventos do webhook do agendamento (ADR-0018), agora também para os destinos da instância.

A entrega é a mesma do webhook do agendamento: assinatura HMAC, `text` em português e saída pelo `check_url`. Cadastrar destino é do owner, como emitir token de integração. O destino tem botão de teste e mostra o último resultado.

## Alternativas descartadas

- **Pedir custo ao provedor depois do fato (API de uso da Anthropic ou da OpenAI).** Chega com atraso de horas, por organização, não por agente, e exige uma chave de administração. Serve para conferir a fatura, não para barrar o próximo run.
- **Orçamento na versão do agente.** Publicar uma versão nova só para mudar o limite misturaria operação com comportamento, e um rollback voltaria o orçamento junto.
- **Barrar no meio do run quando o gasto passar.** Exigiria medir token a token dentro do run e cortar uma resposta já começada. O bloqueio antes do próximo run é previsível e não deixa conversa pela metade.
- **Avisar por e-mail.** Pelo mesmo motivo do ADR-0018: a instância não envia e-mail, e o webhook cobre os canais de chat.
- **Um webhook por evento em cada agente.** Seriam N cadastros iguais. O destino da instância assina eventos uma vez para todos os agentes, e o webhook do agendamento continua para quem quer um canal por agente.

## Consequências

- O custo passa a aparecer com qualquer provedor. É uma estimativa pela tabela, e pode diferir da fatura em cache de prompt, lote e desconto. `MODEL_PRICES` ajusta.
- Atualizar preço é mudança de código ou de variável. Preço errado subestima o gasto e o orçamento.
- Com bloqueio ligado, um agente para de atender quando o orçamento acaba, com a mensagem de bloqueio, até virar o mês ou alguém aumentar o limite. O aviso em 80% existe para isso não pegar ninguém de surpresa.
- O poller ganha mais uma checagem por minuto, que é a taxa de erro recente, numa consulta agregada por config.
- Duas migrations: as colunas de orçamento no `agent_config` e a tabela `alert_destination`, com o estado dos avisos já mandados.

## O que me faria reverter

- Diferença grande e frequente entre o custo estimado e a fatura. Nesse caso, o custo passa a vir da API de uso do provedor, conciliado por dia, e a tabela fica só para o bloqueio.
- Pedido de orçamento por usuário ou por integração, além de por agente. Nesse caso, o orçamento vira uma tabela própria com escopo.
