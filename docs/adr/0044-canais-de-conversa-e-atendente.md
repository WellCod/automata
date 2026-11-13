# ADR-0044 — Canais de conversa e passagem para atendente

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-13

## Contexto

Hoje um agente responde pela API REST, pelo MCP e pelo modo teste do painel. Para chegar ao cliente final, cada empresa escreve a própria ponte entre o WhatsApp ou o Slack e a API, e o que acontece quando o agente não resolve fica fora da plataforma.

O Agno 3.1.8 tem interfaces de WhatsApp e Slack (`agno.os.interfaces`), mas elas recebem um `Agent` ou `Team` montado no boot e leem a credencial do ambiente (`WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`). Isso não serve aqui: os agentes são montados por request a partir da versão vigente ou do canário (ADR-0002, ADR-0040), cada empresa pode ter mais de um número ou workspace, a credencial é cadastrada pelo painel, e não há como uma pessoa assumir a conversa.

O que existe e serve:

- `agent_from`/`team_from` montam o agente com guardrails, orçamento e memória, e o `TrackedAgent` grava o run; o runner da suíte já roda o agente fora da rota com `db` e `session_id` próprios.
- Credencial cifrada com Fernet e rotação (ADR-0026), saída pelo `guarded_client` (ADR-0010), webhook público assinado no app externo (ADR-0039).

## Decisão

**Canal por cadastro.** Tabela `channel` (migration 0058): tipo (`whatsapp` ou `slack`), nome, o agente ou time que responde, credencial cifrada e as opções de passagem para atendente. Workflow fica de fora nesta fase. Só o owner cadastra (scope `channels:admin`), porque a credencial fala em nome da empresa.

- **WhatsApp (Cloud API da Meta):** `access_token`, `phone_number_id`, `app_secret` e `verify_token`.
- **Slack (Events API):** `bot_token` e `signing_secret`.

**Entrada.** Rota pública `/hooks/channels/{id}` no app externo, fora de `/api/v1`, como o webhook da origem dos conectores:

- WhatsApp: `GET` responde o desafio de verificação com o `verify_token`; `POST` só passa com `X-Hub-Signature-256` (HMAC do corpo com o `app_secret`).
- Slack: `X-Slack-Signature` (HMAC `v0`) com timestamp de até 5 minutos; responde o `url_verification`.
- Corpo limitado a 256 KB, lido em stream. A resposta sai na hora (o WhatsApp reenvia o que demora) e a mensagem é processada em segundo plano.
- Mensagem repetida (o provedor reenvia) é descartada pelo id externo único. Só texto: outro tipo recebe uma resposta fixa pedindo texto.
- Limite de 20 mensagens por minuto por pessoa e canal, para um número não queimar o orçamento do agente.

**Conversa.** Tabelas `channel_conversation` e `channel_message`. A conversa é achada pelo canal e por quem fala (o número no WhatsApp; no Slack, o canal e a thread). O `session_id` do agente é o id da conversa, então histórico, memória e canário seguem a conversa. O `user_id` do run é `whatsapp:<número>` ou `slack:<usuário>`, que entra nos pedidos do titular (ADR-0032) junto com as mensagens do canal.

**Resposta.** O agente roda pelo mesmo `agent_from`/`team_from` da rota, com a versão escolhida pelo canário (`canary=True`), guardrails, orçamento e memória. A resposta sai pela API do provedor via `guarded_client`, cortada no limite de cada um (4.096 caracteres no WhatsApp). Erro do agente ou do envio fica na mensagem, com o motivo.

**Atendente humano.** A conversa tem estado `bot`, `human` ou `closed`. Ela passa para `human` em quatro casos:

1. o cliente escreve uma das palavras do canal ("atendente", "humano" por padrão);
2. o agente chama a tool `transferir_para_atendente`, que entra só no run do canal, com a passagem ligada;
3. o run pausa esperando confirmação humana de tool (ADR-0009), que não tem como seguir pelo WhatsApp;
4. alguém assume pelo painel.

Em `human`, o agente não responde. As mensagens aparecem na página **Conversas** do painel, e o atendente responde por ali; a resposta sai pelo canal com o e-mail de quem respondeu gravado. Devolver ao agente ou encerrar volta a conversa ao `bot`. Quem atende precisa de `conversations:handle` (owner e editor).

## Alternativas descartadas

- **Interfaces do Agno.** Agente fixo no boot e credencial no ambiente, sem passagem para humano (ver Contexto).
- **Fila durável para a entrada.** O provedor já reenvia o que não recebe 200, e a mensagem fica gravada antes de o agente rodar; a fila do ADR-0020 serve a runs pedidos pela API.
- **Helpdesk externo (Zendesk, Chatwoot) na passagem.** Mais uma integração por cliente; a fila de conversas no painel cobre o caso de uma equipe pequena. Gatilho de revisão se um cliente já tiver helpdesk.
- **E-mail e Telegram nesta fase.** O WhatsApp é o canal do atendimento no Brasil e o Slack o interno; os outros entram pelo mesmo modelo de canal.

## Consequências

- Rota pública nova, protegida pela assinatura de cada provedor; sem assinatura válida, 401 sem tocar no banco além do canal.
- O WhatsApp só aceita mensagem livre até 24 horas depois da última mensagem do cliente. Resposta do atendente fora da janela falha, e o painel mostra o motivo; modelo de mensagem (template) fica para depois.
- O número de telefone vira `user_id` de run e memória: é dado pessoal, coberto pela exportação e pela exclusão do titular.
