# Integração por API

Referência das rotas que um sistema externo alcança com um **token de integração** (página Integrações, só owner emite). O token vale até 90 dias, carrega só os agentes, times e suítes liberados na emissão e é revogado na hora pelo painel. Use sempre `Authorization: Bearer <token>`.

A API pública é a do painel: `https://<seu-painel>/api/...` repassa para a API interna. As rotas de execução são as do AgentOS (Agno 3.2.1); o formato abaixo é congelado por `api/tests/test_contrato_integracao.py`, e mudança nele sai nas notas da versão.

## Executar um agente

```
POST /agents/{agent_id}/runs
Content-Type: multipart/form-data
```

| Campo | Obrigatório | O que é |
|---|---|---|
| `message` | sim | Texto do usuário |
| `stream` | não | `true` (padrão) devolve SSE; `false` devolve JSON com `content`, `run_id`, `session_id` e `status` |
| `session_id` | não | Conversa a continuar. Sem ele, a API cria uma e devolve o id |
| `factory_input` | não | JSON. `{"end_user": "cliente-42"}` separa a memória de cada pessoa atrás do mesmo token (até 128 caracteres: letras, dígitos e `_.@:+-`) |
| `files` | não | Anexos, quando o modelo aceita |

Times: `POST /teams/{team_id}/runs`, mesmos campos. Workflows: `POST /workflows/{workflow_id}/runs`.

Status do JSON: `COMPLETED`, `PAUSED` (tool com confirmação humana: alguém aprova no painel, em Aprovações), `ERROR`. Bloqueio por guardrail volta como resposta do agente, com a mensagem configurada.

## Limites

- `RUN_RATE_LIMIT_PER_MINUTE` execuções por minuto por token (60 por padrão); acima disso, 429.
- Orçamento mensal do token (US$ 50 por padrão, com bloqueio), editável na página Integrações; estourado, o run volta bloqueado com `budget_exceeded`.
- O run tem o prazo do provedor (120 s por chamada ao modelo) e o limite de chamadas de tool do agente.

## Suíte de testes (CI de quem consome o agente)

Com a suíte liberada no token:

```
POST /api/v1/configs/{config_id}/eval-runs   {"target": "current"}  → 202 com o id
GET  /api/v1/configs/{config_id}/eval-runs/{id}                      → verdict: pass | fail
```

## Pedidos do titular

Com a opção ligada na emissão, o token pede exportação e exclusão só do próprio titular (`integration:<id>` ou `integration:<id>:<end_user>`):

```
POST /api/v1/data-subjects/{user_id}/export
POST /api/v1/data-subjects/{user_id}/erase   {"confirm": "<o mesmo user_id>"}
```

## MCP

Assistentes de IA usam `POST /mcp` (Streamable HTTP) com o mesmo token. As tools `run_agent` e `run_team` só enxergam o que foi liberado.

## Erros

| Código | Quando |
|---|---|
| 401 | Token inválido, vencido ou revogado |
| 403 | Recurso não liberado no token, ou versão específica sem `configs:write` |
| 409 | Aprovação com tool diferente da pendente |
| 429 | Limite de execuções por minuto |
