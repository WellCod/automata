# ADR-0018 — Avisos de regressão da suíte agendada por webhook assinado, só nas mudanças de estado

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-10-21

## Contexto

A suíte agendada (ADR-0016) pega regressão no que muda por fora do prompt: modelo do provedor, base reindexada, servidor MCP. Só que o sinal fica no painel, no selo da lista de agentes. Uma regressão das 3h da manhã só é vista quando alguém abre o painel, e o agendamento rende pouco se ninguém olha.

O ADR-0016 deixou o aviso por webhook ou e-mail para depois.

No código atual:

- O agendamento (`eval_schedule`) é um por config, e o poller cria cada execução com `trigger: schedule`.
- `app/evals/compare.py` já calcula o estado da suíte e as regressões entre execuções agendadas seguidas.
- `app/mcp/egress.py` (`check_url`) recusa URL que não seja https e host que resolva para IP interno, com exceções por `MCP_ALLOWED_HOSTS`. Ele protege as conexões a servidores MCP contra SSRF.
- `app/secrets.py` cifra segredos com Fernet (`MCP_SECRETS_KEY`), como os headers dos servidores MCP.
- A API não tem envio de e-mail: nem SMTP, nem provedor configurado.

## Decisão

**Webhook por agendamento, assinado, disparado só quando o estado muda.** Depois de cada execução agendada, a API compara o estado com o da execução agendada anterior e só avisa nas mudanças:

| Antes                 | Agora                                              | Evento                          |
| --------------------- | -------------------------------------------------- | ------------------------------- |
| verde                 | caso que passava falhou                            | `suite.regressed`, com os casos |
| verde                 | falhou sem regressão (caso novo, erro da execução) | `suite.failing`                 |
| sem execução anterior | falhou                                             | `suite.failing`                 |
| falhando ou regredida | verde                                              | `suite.recovered`               |

Estado igual ao anterior não avisa: uma suíte quebrada há uma semana não manda 28 mensagens.

**Corpo que serve a quem integra e a quem só cola num canal.** O JSON traz:

- o evento, o config (id e nome), a execução e a anterior;
- `passed` e `total`, os casos que regrediram e o instante;
- um campo `text` em português, com o resumo.

Webhooks de entrada de Slack, Microsoft Teams e Discord leem `text`, ou `content` no Discord, que também vai no corpo. Assim funcionam colados sem adaptador.

**Assinatura e segredo.** Cada webhook ganha um segredo gerado pela API, mostrado uma vez, como os tokens de integração. Cada envio leva `X-Automata-Signature: sha256=<HMAC do corpo>` e `X-Automata-Event`. A URL também é cifrada, porque URLs de webhook de Slack e Teams carregam o próprio token no caminho. O painel mostra só o host. Sem `MCP_SECRETS_KEY`, o cadastro é recusado com o motivo, como nos servidores MCP.

**Mesma proteção de saída dos servidores MCP.** A URL passa pelo `check_url` ao ser gravada **e a cada envio**, porque o DNS pode mudar depois do cadastro.

**Entrega em background, com poucas tentativas.** Até 3 tentativas, com 10 s de timeout e espera de 1 s e 5 s entre elas. A resposta 2xx conta como entregue. O agendamento guarda o último resultado (código HTTP ou erro) e a hora, e a aba Testes mostra isso. Falha de entrega nunca afeta a execução da suíte.

**Rotas próprias do webhook, separadas do agendamento.** `PUT /eval-schedule/webhook` cadastra ou troca a URL e devolve o segredo. `DELETE` remove o webhook. `POST /eval-schedule/webhook/test` manda um evento `suite.test` para conferir a integração. Gravar exige `evals:write`, como o agendamento.

## Alternativas descartadas

- **E-mail.** Exigiria SMTP ou um provedor de envio, com credencial, domínio verificado e caixa de saída a monitorar, numa instância single-tenant que hoje não envia nada. O webhook cobre Slack, Teams, Discord e qualquer sistema de alerta, e e-mail pode vir por um desses. Volta à mesa se um cliente pedir sem ter chat corporativo.
- **Avisar a cada execução que falha.** É simples, mas vira ruído na segunda semana, e o canal é silenciado. Mudança de estado é o que alguém precisa saber.
- **Webhook por instância, em vez de por agendamento.** Um canal só para todos os agentes mistura times diferentes. Por agendamento, cada agente avisa quem cuida dele. Um canal comum é só colar a mesma URL em vários.
- **Fila com retry longo (outbox).** Garante entrega depois de horas fora do ar, mas pede tabela de pendências e worker. Aviso atrasado em horas perde o valor. Três tentativas e o último resultado visível bastam no começo.

## Consequências

- Quem cuida do agente fica sabendo da regressão no canal do time, minutos depois do horário agendado.
- A URL e o segredo ficam cifrados com a mesma chave dos servidores MCP. Rotacionar `MCP_SECRETS_KEY` exige recadastrar os webhooks, como os servidores.
- A API passa a fazer chamadas de saída por conta própria, e não só para servidores MCP. A proteção é a mesma, e host interno só entra pela allowlist.
- Execução manual ou por token de integração não avisa. O aviso é do agendamento, que tem origem e alvo fixos e um histórico comparável.
- Uma migration: colunas do webhook no `eval_schedule`.

## O que me faria reverter

- Pedido de alerta para outras coisas além da suíte, como run com erro, bloqueio por guardrail ou custo acima do limite. Nesse caso, um cadastro de destinos de aviso por instância, com eventos assináveis, substitui o webhook do agendamento.
- Perda de aviso por API fora do ar no momento da entrega. Nesse caso, a fila com retry passa a valer o custo.
