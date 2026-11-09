# ADR-0036 — Pedido do titular por integração e pelo próprio usuário, com prazo e aviso

**Status:** Aceito
**Data:** 2026-11-04

## Contexto

O ADR-0032 deu ao owner a consulta, a exportação e a exclusão dos dados de um titular. Ficaram para depois três coisas:

- **O titular não pede sozinho.** Quem fala com o agente pelo aplicativo de uma empresa pede os dados ao aplicativo. Hoje a empresa precisa abrir um chamado para o owner da instância, que copia o id e faz o pedido no painel.
- **Quem usa o painel também é titular.** O run do modo teste grava o `user_id` de quem conversa (o `sub` do token, ADR-0024). Esse usuário não tem como ver ou apagar o que a instância guardou dele.
- **Sem prazo.** A LGPD (art. 19, II) dá 15 dias para a resposta completa. O pedido roda em background e costuma terminar em segundos, mas um pedido que falha fica parado sem ninguém saber.

## Decisão

**Pedido por token de integração.** O token de integração ganha a opção `data_subjects`, que dá o scope `data_subjects:request`. Com ele, o sistema da empresa usa as mesmas rotas do owner:

- `GET /api/v1/data-subjects/{user_id}`;
- `POST .../export` e `POST .../erase`, que exige o `confirm` repetindo o id;
- `GET /api/v1/data-subject-requests`;
- `.../download`.

Ele vê e baixa só os pedidos que ele mesmo fez (`requested_by = integration:<id>`).

**Revisão da Fase 43.** O token só pede pelo próprio titular, `integration:<id>`. A premissa original era que o `user_id` vinha do sistema da empresa, mas com `user_isolation` o Agno grava todo run de integração com o `sub` do token. Aceitar qualquer id dava ao token as conversas de outras integrações e do painel. Para separar os clientes finais de uma integração, cada sistema precisa de um token próprio.

**Pedido pelo próprio usuário do painel.** `GET /api/v1/me/data` conta o que há do usuário logado. `POST /api/v1/me/data/export` e `POST /api/v1/me/data/erase` pedem a exportação e a exclusão. A exclusão exige o e-mail do usuário repetido. Os pedidos dele aparecem em `GET /api/v1/me/data/requests`, e o download só serve ao dono do pedido. A conta do painel continua existindo: o que sai é o dado de conversa, memória e consumo, como no ADR-0032.

**Prazo e aviso.** O pedido ganha `source` (`panel`, `integration` ou `self`) e `due_at`, que é a criação mais `DATA_SUBJECT_DEADLINE_DAYS` (15 por padrão), na migration 0045. O poller de alertas avisa nos destinos da instância (ADR-0021):

- `data_subject.failed`: o pedido falhou. A exclusão não guarda o id, então o aviso pede para refazer o pedido;
- `data_subject.due`: o pedido segue na fila ou rodando a 2 dias do prazo, ou depois dele.

Cada pedido avisa uma vez por evento. A lista de pedidos mostra o prazo, a origem e os vencidos em destaque.

## Alternativas descartadas

- **Token de integração com acesso a qualquer titular.** Foi a decisão original, revista na Fase 43: o `user_id` dos runs de integração é o do token, não o do sistema da empresa, então o acesso amplo só servia para ler dado de outros.
- **Pedido do titular entrando como pendente de aprovação do owner.** A LGPD não pede intermediário, e a confirmação repetindo o id já evita o pedido por engano.

## Consequências

- Um token com `data_subjects` exporta os dados de qualquer titular. A opção fica desligada por padrão, e o owner vê quais tokens a têm.
- A exclusão pelo próprio usuário do painel não apaga a conta. Para isso, o owner remove o usuário (ADR-0024).
