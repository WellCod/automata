# automata — api

API em Python sobre o Agno AgentOS.

## Dependências principais

| Pacote | Versão pinada | Licença |
|--------|--------------|---------|
| agno[os,mcp] | 3.1.8 | Apache 2.0 |
| psycopg[binary] | ≥3.2 | LGPL-3.0 |
| alembic | ≥1.14 | MIT |
| pydantic-settings | ≥2.7 | MIT |

A licença do Agno na versão 3.1.8 é **Apache 2.0**, confirmada em `github.com/agno-agi/agno/blob/main/LICENSE`. ADR-0007 registrava incerteza entre MPL-2.0 e Apache-2.0 — resolvida: é Apache 2.0, compatível com AGPL-3.0 para fins de distribuição.

## Rodando local

Para desenvolvimento, a API roda em Docker junto com o banco. A partir da raiz do repositório:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

A API sobe em `http://localhost:8000` com hot-reload ativo e `APP_ENV=development`. As migrations rodam automaticamente no boot: o `entrypoint.sh` roda `alembic upgrade head`, depois `python -m app.agno_migrations` e só então executa o `command:` do compose (sem ele, o `CMD` da imagem: uvicorn sem reload). Fora do override de dev a porta 8000 não é publicada.

O Alembic cuida só das tabelas do Automata. As do Agno, no schema `ai`, têm versão própria e são migradas pelo `MigrationManager` do Agno em `app/agno_migrations.py`. Na v3, os runs saíram do JSON da sessão para `ai.agno_runs`. A migração é idempotente e não apaga nada: a coluna antiga `runs` de `ai.agno_sessions` fica como backup. Removê-la (`cleanup_legacy_runs_column`) é decisão manual, depois de conferir o histórico e ter um backup restaurável.

Para rodar isolado (sem Docker), com banco já acessível via `DATABASE_URL`:

```bash
cd api
uv sync
APP_ENV=development uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`/docs`, `/redoc` e `/openapi.json` só existem com `APP_ENV=development`; o padrão é `production`, que os desliga. Os tipos do painel não dependem dessas rotas: `scripts/export_openapi.py` gera o schema com `app.openapi()`.

## Evals de confiabilidade

Dois níveis de cobertura:

| Suite | Quando roda | Como rodar |
|---|---|---|
| Smoke | Todo PR (CI) | `pytest -m "not nightly"` |
| Noturna | Diariamente às 03:00 UTC | `pytest -m nightly` |

A suite smoke testa a lógica do `ReliabilityEval` com `RunOutput` construído manualmente — sem custo e sem dependência de credencial. A suite noturna chama LLM real (Claude Haiku) e verifica que o agente chama as tools esperadas. Requer `ANTHROPIC_API_KEY` no ambiente.

Arquivos:
- `tests/test_evals_smoke.py` — fixtures gravadas, sem LLM
- `tests/test_evals_nightly.py` — evals com LLM real, marcados `@pytest.mark.nightly`
- `tests/test_evals_guardrails.py` — 30 mensagens com a regra que deveria barrar cada uma ou nenhuma: CPF, CNPJ, cartão, e-mail e telefone; injeção em PT e EN; tópicos e tamanho. Um terço são casos que precisam passar (número de pedido, protocolo, "instruções para trocar a senha", "política de reembolso"). Sem LLM, roda em todo PR; mudou lista ou padrão, entra caso novo.
- `tests/test_evals_workflows.py` — regras de condição sobre respostas reais de triagem e mensagens de cliente, condição que lê a resposta do ramo e não o resumo que o Agno põe depois de um paralelo, parada de repetição e estrutura aceita ou recusada (o workflow do critério de aceite, 3 níveis, 30 etapas, terminar em paralelo, regra sem texto). Casos de limite documentam o que regra por texto não resolve: "não quero reembolso" casa com `contém reembolso`, e "reembolsado" não. Sem LLM, roda em todo PR.
- `tests/test_evals_suite.py` — a suíte de testes por agente sobre ela mesma: scorer de texto sobre respostas reais, montagem do `Case` do Agno (juiz só quando há modelo, nunca no modo demo; caso só com juiz indisponível não monta o agente), tradução do `CaseResult` em status (erro e timeout viram `error`), veredito do gate (não avaliado trava, execução rodando ou falha também) e comparação entre execuções. Sem banco nem LLM, roda em todo PR.
- `tests/test_evals_retrieval.py` — recuperação das bases de conhecimento sobre os documentos e perguntas de `app/knowledge/demo_content.py`: o documento certo precisa voltar entre os 3 primeiros trechos. A versão literal roda em todo PR com o embedder local; a semântica (perguntas com outras palavras) roda na noturna com a Voyage, exige `VOYAGE_API_KEY` e aceita recall@3 de 80%.
- `.github/workflows/evals-nightly.yml` — workflow agendado

## Metering

`GET /api/v1/usage/rollup?period=YYYYMM&agent_id=<uuid>` — retorna consumo agregado por agente no período.

O rollup agrega tokens e custo por `(agent_config_id, period)`. Campos: `run_count`, `input_tokens`, `output_tokens`, `total_tokens`, `cost`.

`GET /api/v1/metrics/timeseries?period=30d|start=&end=&agent_id=<uuid>` — um ponto por dia (UTC) com `total_runs`, `error_count`, `p50_ms`, `p95_ms`, `total_tokens` e `total_cost`. Dia sem execução vem zerado, com latência e custo nulos. Limite de 366 dias. Alimenta os gráficos do analytics e da aba Desempenho do agente.

## Runtime de agentes

- **Factory por request** (`app/agents/factory.py`): lê a versão vigente (ou a `version_id` do modo teste, que precisa ser do mesmo agente — outra versão dá 400) e monta o `Agent`. Leitura do banco fora do event loop.
- **Histórico da sessão**: agente e líder de time levam ao modelo os últimos 5 turnos da mesma `session_id` (`add_history_to_context`, `HISTORY_RUNS` na factory). O padrão do Agno é não levar nenhum, e até a Fase 17 cada mensagem de uma conversa chegava sozinha ao modelo. O histórico sai do banco que o `AgentFactory` injeta no agente, então um `Agent` montado sem `db` não tem memória.
- **Compactação de conversa** (ADR-0019): `conversation` no payload versionado, desligado por padrão. Com `compaction: true`, a factory liga a `Compaction` do Agno com `compact_at_tokens` (padrão 16 mil, de 4 mil a 128 mil), `keep_recent_runs` (turnos inteiros, padrão 3), `summary_instructions` e `search_history`, a tool de busca no histórico compactado. Acima do limite, os turnos antigos viram um resumo feito pelo modelo do próprio agente, e o consumo dele entra nos totais do run. Com a compactação ligada, a janela vai até o limite, e o `HISTORY_RUNS` deixa de valer. Só agente: o `Team` do Agno 3.1.8 não aceita, e time com a opção dá erro na escrita.
- **Memória do usuário** (ADR-0025, `app/agents/memory.py`): `memory` no payload versionado, com `enabled` (desligado por padrão), `instructions` (até 500, o que vale lembrar) e `retention_days` (1 a 365, padrão 90). Ligada, o agente usa o `update_memory_on_run` do Agno: no fim do run, o modelo do próprio agente extrai fatos sobre o usuário, e o consumo entra no run. Diferenças do padrão do Agno: o `AgentMemoryManager` lê pelo par usuário e agente, porque o do Agno lê só por usuário e mostraria a um agente o que o outro guardou; run sem `user_id` e run da suíte de testes ficam sem memória, porque o Agno usaria o usuário `"default"` para todos os anônimos; o banco da memória (`MaskingDb`) mascara PII de todos os tipos no texto e na mensagem de origem antes de gravar, e as instruções de captura proíbem documento, cartão, senha e dado de saúde. As memórias ficam na tabela do Agno (`agno_memories`). Só agente: time com a opção dá erro na escrita.
  - Retenção e exclusão (`app/agents/memory_admin.py`): de hora em hora, o poller apaga as memórias de cada agente mais velhas que o `retention_days` da versão vigente, contando da última atualização. Desligar a memória não apaga nada; o que foi guardado vence pelo prazo. O owner vê e apaga por agente em `/api/v1/configs/{id}/memories` (`?user_id=` filtra; `DELETE` com `user_id` apaga tudo do usuário naquele agente). Cada usuário vê as próprias, com o nome do agente, e apaga uma ou todas em `/api/v1/me/memories`. Memória de outra pessoa responde 404.
- **Registro sem restart** (`app/agents/registry.py`): a lista de agentes do AgentOS é sincronizada com os configs publicados no boot, logo após cada publicação e, com TTL de 5 s, antes de requests a `/agents`, `/teams`, `/mcp` e `/config` — o que cobre publicações feitas em outro worker.
- **Lifespan do AgentOS**: o AgentOS fica montado dentro do app externo, que tem as rotas públicas (`/login`, `/health`), e o Starlette não roda lifespan de app montado. O lifespan do app externo (`_lifespan_for` em `app/main.py`) entra no do AgentOS. Sem isso, o servidor MCP (`/mcp`) respondia 500, "Task group is not initialized", e o provisionamento do banco, a fila de background e o cliente HTTP do Agno não subiam. A telemetria de lançamento do AgentOS fica desligada (`telemetry=False`).
- **Fila durável** (ADR-0020): run com `background=true` vira uma linha em `ai.agno_jobs`, a fila durável do Agno no Postgres da instância (`background_queue` em `app/background.py`). O worker sobe no lifespan do AgentOS, um por réplica, e resolve o agente pelo nosso factory. É uma tentativa só, porque tool com efeito pode ter rodado antes da queda, e 15 minutos por execução. Os dois valores ficam fixos no código, porque o Agno exige o mesmo valor em todas as réplicas. Com `REDIS_URL`, cancelar e acompanhar o stream funcionam de qualquer réplica. `BACKGROUND_QUEUE_DURABLE=false` volta às tasks em memória. Mais de mil pendentes dão 429.
- **Registro de execução** (`app/agents/tracking.py`): o `TrackedAgent` envolve `arun` e `acontinue_run` e grava em `agent_run` o desfecho real — `success`, `error`, `cancelled` ou `paused` — com duração e erro, e em `usage_event` os tokens e o custo, na mesma transação. Run pausado e retomado atualiza a mesma linha (por `run_id`). Post-hooks do Agno não serviam: só rodam quando o run termina bem. Runs com `background=true` também são registrados: o worker da fila durável roda o mesmo agente do factory.
- **Custo estimado** (ADR-0021, `app/pricing.py`): o Agno só preenche `metrics.cost` quando o provedor informa, e a Anthropic e a OpenAI devolvem só tokens. Sem custo informado, o tracking, o juiz da suíte e o HyDE calculam pelos tokens com o preço de referência de cada modelo, em dólar por milhão. `MODEL_PRICES` (JSON) sobrescreve modelo a modelo, e um JSON inválido cai na tabela com aviso no log. Modelo sem preço fica sem custo, sem valor inventado. `GET /api/v1/models/prices` devolve a tabela em uso.
- **Orçamento mensal** (ADR-0021, `app/budget.py`): `GET`/`PUT /api/v1/configs/{id}/budget` com limite em dólar, aviso em % (padrão 80) e bloqueio opcional. Fica no `agent_config`, fora da versão. O gasto é a soma do `usage_event` do config no mês corrente, com testes e HyDE. Com bloqueio ligado, um hook antes dos guardrails barra o run como `blocked` (`budget_exceeded`) sem chamar o modelo, com cache de 30 s do gasto. Membro de time não tem orçamento próprio: conta no time. Ler pede `metrics:read`; mudar, `configs:write`.
- **Destinos de aviso** (ADR-0021, `app/alerts.py`): `/api/v1/alert-destinations` cadastra webhooks da instância, com URL e segredo cifrados como o webhook da suíte e o segredo mostrado uma vez. Cada destino assina eventos: `budget.warning` e `budget.exceeded` (uma vez por config e por mês em cada nível), `errors.spike` (50% ou mais de erro em pelo menos 5 runs de conversa nos últimos 15 min, no máximo um por config por hora) e os `suite.*` do agendamento. O poller das suítes confere orçamento e erro a cada minuto. A tabela `alert_sent`, com chave única por config, evento e janela, impede aviso repetido entre réplicas. Sem destino assinando o evento, nada é reservado. Só owner (`integrations:write`).
- **Tools MCP** (ADR-0010): o payload v2 traz `mcp_servers: [{server_id, tools, require_confirmation}]`, em que `tools: null` libera todas as tools do servidor. A factory monta um `MCPTools` por servidor, com prefixo pelo slug (`crm_buscar_cliente`) e só as tools liberadas. O `TrackedAgent` conecta todos **antes** do run, na mesma task, e registra as conexões para o próprio Agno fechá-las no fim. Se um servidor não conecta, o run termina com `status=ERROR` (ou `RunError` no stream) dizendo qual servidor falhou, e fica gravado como `error`. O agente nunca responde sem as tools que deveria ter.
- **Validação na escrita**: o servidor precisa existir, e as tools liberadas e as que pedem confirmação precisam constar no retrato descoberto, quando ele existe. Confirmação só vale para tool liberada (422).
- **Payload v1** (`tools: list[str]`, que nunca teve efeito) é convertido para v2 na leitura. Versões antigas seguem legíveis e o próximo rascunho já sai em v2.
- **Capabilities**: `extended_thinking` liga `thinking` no Claude (budget de 4096 tokens). Visão depende só do modelo; `structured_output` ainda não tem efeito porque o config não guarda `output_schema`.

## Scopes JWT

Autenticação por JWT assimétrico RS256. O backend emite o token (via `app.auth.issue_token`), o AgentOS verifica usando a chave pública de `JWT_PUBLIC_KEY`, configurada no `Authorization` de `agno.os.authz` (o `AuthorizationConfig` solto foi descontinuado na v3). Os scopes vêm do token, sem papéis gerenciados pelo Agno. `AgentOS(user_isolation=True)` ativo: cada usuário só enxerga suas próprias sessões e memórias.

| Scope | Descrição |
|---|---|
| `agent_os:admin` | Acesso total — todos os endpoints |
| `agents:read` | Listar e ler agentes |
| `agents:write` | Criar e editar agentes |
| `agents:*:run` | Executar qualquer agente |
| `agents:<id>:run` | Executar agente específico |
| `sessions:read` | Ver sessões |
| `sessions:write` | Criar e atualizar sessões |
| `sessions:delete` | Apagar sessões |
| `memories:read` | Ver memórias |
| `memories:write` | Criar e atualizar memórias |
| `memories:delete` | Apagar memórias |
| `traces:read` | Ver traces |
| `config:read` | Ler configuração da OS |
| `config:write` | Operações administrativas (ex: migrations) |
| `evals:read` | Ver execuções de evals |
| `evals:write` | Criar e atualizar evals |
| `service_accounts:read` | Listar service accounts |
| `service_accounts:write` | Emitir tokens de service account |

### Rotas próprias (`/api/v1/*`)

O middleware do AgentOS valida a assinatura em todas as rotas, mas só exige scope nas do mapa padrão dele. As rotas próprias declaram o scope com `require_scopes` (`app/authz.py`), que usa a mesma regra de casamento do Agno (`agent_os:admin` libera tudo).

| Scope | Rotas |
|---|---|
| `configs:read` | `GET /api/v1/configs`, `GET /api/v1/configs/{id}`, `GET /api/v1/configs/{id}/versions`, `GET /api/v1/models/capabilities`, `POST /api/v1/linter` |
| `configs:write` | `POST /api/v1/configs`, `PUT /api/v1/configs/{id}/draft`, `POST /api/v1/mcp-servers/{id}/discover` |
| `configs:publish` | `POST /api/v1/configs/{id}/publish`, `POST /api/v1/configs/{id}/rollback` |
| `metrics:read` | `GET /api/v1/configs/{id}/runs`, `GET /api/v1/configs/{id}/metrics`, `GET /api/v1/metrics/*`, `GET /api/v1/usage/rollup`, `GET /api/v1/approvals`, `GET /api/v1/runs/{run_id}/trace` (este só para o dono do run ou owner) |
| `mcp_servers:read` | `GET /api/v1/mcp-servers`, `GET /api/v1/mcp-servers/{id}` |
| `mcp_servers:write` | `POST`, `PUT` e `DELETE` em `/api/v1/mcp-servers` — só owner (`agent_os:admin`) |
| `knowledge_bases:read` | `GET /api/v1/knowledge-bases`, `GET /api/v1/knowledge-bases/{id}`, `GET /api/v1/knowledge-bases/embedders`, `GET /api/v1/knowledge-bases/{id}/contents[/{content_id}]`, `POST /api/v1/knowledge-bases/{id}/search` |
| `knowledge_bases:write` | `POST`, `PUT` e `DELETE` em `/api/v1/knowledge-bases`; `POST /contents/file`, `/url` e `/text` e `DELETE /contents/{content_id}` |
| `evals:read` | `GET /api/v1/configs/{id}/eval-cases`, `GET /api/v1/configs/{id}/eval-runs[/{run_id}]`, `GET .../eval-runs/compare`, `GET /api/v1/configs/{id}/eval-settings` |
| `evals:write` | `POST`, `PUT` e `DELETE` em `/api/v1/configs/{id}/eval-cases`; `PUT /api/v1/configs/{id}/eval-settings` |
| `evals:run` | `POST /api/v1/configs/{id}/eval-runs` |
| `evals:<id>:read`, `evals:<id>:run` | As mesmas rotas de `eval-runs`, só para aquele config. Vêm nos tokens de integração com `eval_ids`; a checagem é o `require_resource_scope` de `app/authz.py`, que aceita o escopo global ou o do `config_id` da rota |
| `knowledge_connectors:write` | `POST`, `PUT` e `DELETE` em `/api/v1/knowledge-bases/{id}/connectors` (ADR-0024) — só owner. Testar e sincronizar pedem `knowledge_bases:write` |
| `memories:admin` | `/api/v1/configs/{id}/memories`: listar por usuário, apagar uma e apagar todas de um usuário (ADR-0025) — só owner |
| `users:admin` | `/api/v1/users` (listar, criar, alterar papel e situação, redefinir senha, remover) — só owner (`agent_os:admin`) |
| `agent_os:admin` | `POST /api/v1/auth/users`; `integrations:write` (rotas `/api/v1/integrations`) só vem pelo admin |

`POST /api/v1/auth/login` e `GET /health` são públicos. `GET /api/v1/me` vale para qualquer token e devolve id, e-mail e papel (token de integração volta só o `sub`). `/api/v1/me/memories` também: lista e apaga as memórias que os agentes guardaram sobre quem está logado (ADR-0025).

### Papéis

Definidos em `ROLE_SCOPES` (`app/schemas/user.py`) e gravados no token no login. Mudança de papel vale a partir do próximo login.

| Papel | Scopes |
|---|---|
| `owner` | `agent_os:admin` |
| `editor` | tudo do viewer + `agents:run`, `teams:run`, `workflows:run`, `sessions:write`, `configs:write`, `configs:publish`, `knowledge_bases:write`, `evals:write`, `evals:run` |
| `viewer` | `agents:read`, `teams:read`, `workflows:read`, `sessions:read`, `traces:read`, `configs:read`, `metrics:read`, `mcp_servers:read`, `knowledge_bases:read`, `evals:read` |

### Gestão de usuários

Página **Usuários** do painel, só para owner, sobre `/api/v1/users`:
- Mudar papel, desativar ou redefinir senha grava `user_account.tokens_valid_after` e encerra na hora as sessões abertas: o `RevocationMiddleware` recusa token do usuário com `iat` anterior ao corte (cache de 30 s nos outros workers). O corte vale até o fim do segundo da mudança, porque `iat` é em segundos inteiros.
- A instância precisa de ao menos um owner ativo: rebaixar ou desativar o último dá 409.
- Remover exige usuário desativado (o corte de sessão acontece na desativação) e não vale para a própria conta.
- `last_login_at` é gravado a cada login.

### Chaves

A chave privada (`JWT_PRIVATE_KEY`) existe só no processo da API, que emite os tokens. O painel recebe apenas `JWT_PUBLIC_KEY` para verificar o cookie no proxy (ADR-0005). Os testes geram um par em memória.

### Rate limit do login

5 tentativas por minuto por e-mail e 20 por IP. O IP vem de `X-Forwarded-For` só quando a conexão chega de um proxy listado em `TRUSTED_PROXIES` (IPs ou CIDRs); o header é lido da direita para a esquerda e vale o primeiro hop fora da lista. Sem `TRUSTED_PROXIES`, vale o IP da conexão. O BFF repassa o IP do cliente na rota `/api/auth/login` e descarta cabeçalhos de encaminhamento vindos do browser no proxy genérico, que também recusa `v1/auth/login`.

E-mail inexistente ou usuário inativo também passa pelo argon2, contra um hash fixo gerado no import de `app/services/user.py`: a latência do 401 não revela quais contas existem.

### Logout

Todo token emitido leva um `jti`. `POST /api/v1/auth/logout` (com o bearer da sessão) grava o `jti` em `revoked_token` até o token expirar, e o `RevocationMiddleware` passa a recusá-lo com 401, nas rotas próprias e nas do AgentOS. Os outros tokens do mesmo usuário continuam válidos. O BFF chama essa rota em `/api/auth/logout` e apaga o cookie mesmo se a API não responder. Token emitido antes do `jti` existir recebe 204 sem ser revogado e expira sozinho em até 1 h. Linhas expiradas saem da tabela a cada logout.

### HSTS

`Strict-Transport-Security` vai em toda resposta servida por HTTPS. Atrás de um proxy que termina o TLS, a conexão chega em HTTP; nesse caso vale o `X-Forwarded-Proto: https`, aceito só quando o peer está em `TRUSTED_PROXIES` (mesma regra do `X-Forwarded-For`, em `app/proxy.py`).

## Servidores MCP externos

Cadastro dos servidores MCP que os agentes consomem (ADR-0010). Não é versionado: alterar URL ou credencial vale na hora para todo agente que usa o servidor.

- `GET|POST /api/v1/mcp-servers`, `GET|PUT|DELETE /api/v1/mcp-servers/{id}`. Escrita só para owner.
- Campos: `name`, `slug` (prefixo das tools, `^[a-z][a-z0-9_]{1,30}$`), `url`, `timeout_seconds` (1–120) e `headers`.
- `headers` é só escrita: os valores são cifrados com Fernet (`MCP_SECRETS_KEY`) e a resposta traz apenas `header_names`. No `PUT`, `headers: null` mantém o que está salvo e `{}` apaga.
- Só `streamable-http`, sem `stdio`. A URL precisa ser `https` e não pode resolver para rede privada, loopback ou link-local (inclui `169.254.169.254`), a não ser que o host esteja em `MCP_ALLOWED_HOSTS` — aí `http` também é aceito. A checagem roda ao salvar e de novo ao conectar.
- Trocar a URL descarta as tools descobertas, que valiam para o endereço antigo.
- `POST /api/v1/mcp-servers/{id}/discover` conecta, lista as tools (nome, descrição e schema de entrada, sem o prefixo) e salva o retrato usado pelo painel. Exige `configs:write`, porque quem edita agente precisa da lista atualizada, e não muda URL nem credencial. Servidor fora do ar, credencial recusada ou URL bloqueada respondem 502 com o motivo.
- A conexão é estrita (`app/mcp/client.py`). O `MCPTools.connect()` do Agno engole a falha e o agente seguiria sem as tools. Em 401 ou conexão recusada, o cliente streamable-http ainda cancela a task que conectou. `connect_strict` converte os dois casos em `McpUnavailable` e só repassa cancelamento que venha de fora.

Gerar a chave: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Perder a chave obriga a recadastrar os headers.

## Confirmação humana de tools

Tools marcadas em `require_confirmation` no agente pausam o run antes de executar (`status=PAUSED`, evento `RunPaused`). O `TrackedAgent` grava o run como `paused`, com o `session_id` e as tools pendentes (`ToolExecution` serializado) em `agent_run.pending_tools`.

- `GET /api/v1/approvals[?agent_id=]` lista os runs pausados com agente, quem pediu, nome e argumentos de cada tool. Cada item traz `kind`, e os de workflow vêm com `steps` (etapas esperando revisão, ADR-0023) no lugar de `tools`.
- A decisão é o continue do próprio AgentOS: `POST /agents/{id}/runs/{run_id}/continue`, com `session_id` e `tools` = os `tool_execution` recebidos, cada um com `confirmed: true` ou `false`. Exige `agents:run`. Com `user_isolation`, só o dono da sessão ou um owner retoma.
- Aprovado, a tool executa e o run segue. Rejeitado, o modelo recebe a recusa e responde sem a ação. Nos dois casos o mesmo `agent_run` passa a `success`, e a pendência some.

## Times multi-agente

Time é um config com `kind: "team"` (ADR-0011), criado com `POST /api/v1/configs` e `"kind": "team"`. Usa o mesmo ciclo de rascunho, publicação, rollback, versões, execuções e métricas do agente. `GET /api/v1/configs?kind=agent|team` filtra.

- Payload: `model_id`, `instructions` e `mcp_servers` são do **líder**. A seção `team` traz:
  - `mode`: `coordinate` (padrão), `route`, `broadcast` ou `tasks`;
  - `members`: `[{agent_id, version_id?}]`, de 1 a 20;
  - `max_iterations` e `share_member_interactions`.
- Membro sem `version_id` segue a versão vigente do agente; com `version_id`, fica fixado nela.
- A descrição do agente vira o `role` do membro, que é o que o líder lê para decidir a quem delegar.
- Validação na escrita: os membros existem, são agentes (sem time dentro de time) e estão publicados. A versão fixada precisa ser publicada e do próprio agente. Agente não aceita seção `team`.
- Runtime: `TeamFactory` por request; o time é registrado em `os.teams` sem restart, como os agentes. Roda em `POST /teams/{id}/runs` e exige `teams:run` (editor e owner). O `TrackedTeam` conecta de forma estrita o MCP do líder e dos membros antes do run.
- `GET /api/v1/configs/{id}/teams` lista os times cuja versão vigente ou rascunho tem o agente como membro. Publicar o agente muda o comportamento deles.
- Só o run do time vai para `agent_run`/`usage_event`, com o consumo somado dos membros. Os membros não ganham run próprio, para o custo não contar duas vezes.

## Integrações (tokens de consumidor)

Tokens para sistemas externos e assistentes de IA chamarem agentes e times via REST ou `/mcp` (ADR-0009). Só owner emite, lista e revoga.

- `POST /api/v1/integrations` recebe `{name, agent_ids, team_ids, eval_ids, expires_in_days}` (até 90 dias) e devolve o token **uma vez só**, junto com o `mcp_url` (`PUBLIC_BASE_URL` + `/mcp`).
- O token carrega só `agents:<id>:read|run` e `teams:<id>:read|run` dos recursos liberados, com `sub = integration:<id>` e um `jti`. Ele lista e executa apenas esses recursos, e não acessa config, métricas nem sessões de outros. Os recursos precisam estar publicados.
- `eval_ids` (ADR-0016, migration 0024): agentes e times cuja suíte de testes o token pode rodar e consultar, para o CI de quem consome o agente. O token ganha `evals:<id>:read` e `evals:<id>:run` só para esses, e não lê nem edita casos, não mexe no gate e não publica. Não exige versão publicada, porque a suíte pode rodar no rascunho; workflow não entra. Um token pode ter só `eval_ids`. A execução disparada por ele fica com `trigger: integration` e `started_by: integration:<id>`.
- `GET /api/v1/integrations` lista sem o token. `DELETE /api/v1/integrations/{id}` revoga.
- Revogação: o Agno só valida assinatura e expiração, então o `RevocationMiddleware` (`app/integrations.py`) recusa com 401 o `jti` revogado (de integração ou de sessão encerrada no logout) antes de a request chegar a ele. No processo que revogou, vale na hora; nos outros workers, em até 30 s (cache).
- No `/mcp`, as tools `run_agent`/`run_team` exigem os mesmos scopes por recurso da REST, e `get_agentos_config` lista só o liberado.

## Bases de conhecimento (RAG)

Fase 13 ([ADR-0012](../docs/adr/0012-bases-de-conhecimento.md)). Ingestão, busca e uso pelos agentes vêm nos próximos PRs.

- **Cadastro** (`/api/v1/knowledge-bases`): nome, slug (vira o nome da tool de busca do agente e não muda depois), descrição (o agente lê para decidir quando buscar) e tamanho de trecho (vale para novas ingestões). O embedder é escolhido na criação, com padrão em `KNOWLEDGE_DEFAULT_EMBEDDER`, e fica fixo com modelo e dimensões: trocar exige recriar a base. Criar com embedder sem chave dá 422 dizendo qual variável falta; `DEMO_REPLAY=true` libera sem chave.
- `GET /api/v1/knowledge-bases/embedders` lista os embedders, se a chave está configurada e qual é o padrão, para o painel.
- Cada base tem a própria tabela de vetores no schema `ai` (`kb_<id>`), criada pelo Agno na primeira ingestão. Remover a base apaga a tabela e os conteúdos.
- **Conteúdo** (`/api/v1/knowledge-bases/{id}/contents`): `POST /file` (multipart, extensões de `KNOWLEDGE_ALLOWED_EXTENSIONS`, até `KNOWLEDGE_MAX_UPLOAD_MB`; 415 e 413 fora disso), `POST /url` e `POST /text` respondem 202 com o conteúdo em `processing`. Uma thread da própria API lê, quebra em trechos (recursivo, `chunk_size` da base com 10% de sobreposição), gera os embeddings e grava; o estado vira `completed` (com `chunk_count`) ou `failed` com o motivo. `GET` lista e lê o estado; `DELETE` apaga os trechos e o registro.
- O estado fica em `knowledge_content`, não no `contents_db` do Agno. Cada trecho leva `content_id` e `source` no metadado, o que permite apagar por documento e citar a fonte.
- O `insert` do PgVector pula em silêncio trecho cujo embedding falha. A ingestão embeda o primeiro trecho antes, para o erro real (chave inválida, cota) virar a mensagem, e confere a contagem depois: faltou trecho, apaga o que entrou e marca falha.
- URL: checagem de SSRF dos servidores MCP (ADR-0010) ao receber e de novo a cada redirect, seguido à mão (até 3). Tipos aceitos pelo `Content-Type`: PDF, DOCX, Markdown, texto, CSV, JSON e HTML; HTML vira texto sem script, estilo, menu e rodapé.
- Restart no meio deixa o conteúdo em `processing`; no boot, o que está assim há mais de 30 minutos vira `failed` ("reenvie").
- **Conectores** (ADR-0024, migration 0033, `/api/v1/knowledge-bases/{id}/connectors`): `github` (`repo`, `branch`, `path`, `api_url` para GitHub Enterprise; token opcional), `s3` (`bucket`, `region`, `prefix`, `endpoint_url` para MinIO; chave opcional, sem ela vale a credencial da máquina) e `sharepoint` (`hostname`, `site_path`, `folder_path`, `tenant_id`, `client_id`; `client_secret` obrigatório). O segredo é cifrado com `MCP_SECRETS_KEY` e a API só diz `has_secret`. `api_url` e `endpoint_url` passam pelo filtro de saída no cadastro e a cada chamada. Cadastrar, trocar e apagar pede `knowledge_connectors:write`, que só o owner tem; testar e sincronizar pede `knowledge_bases:write`.
  - O download é nosso (`app/knowledge/sources.py`): REST do GitHub (árvore do branch e conteúdo bruto), Microsoft Graph com client credentials pelo `httpx` e `boto3` no S3. Os loaders remotos do Agno gravam pelo `Knowledge` dele, sem `content_id` por trecho e sem medir o embedder.
  - `POST .../{id}/test` lista a origem sem baixar e diz quantos arquivos entrariam. `POST .../{id}/sync` responde 202 e roda em background (409 se já estiver rodando).
  - A sincronização (`app/knowledge/connector_sync.py`) compara pela versão remota (sha do Git, ETag do S3, eTag do Graph) guardada em `knowledge_content.external_version`: arquivo novo entra, versão mudada perde os trechos e é reindexada, arquivo que sumiu sai com os trechos, versão igual não baixa. Só extensões que a ingestão lê, até 500 arquivos e `KNOWLEDGE_MAX_UPLOAD_MB` por arquivo; o resto conta como `skipped` no `last_summary`.
  - Apagar o conector apaga os conteúdos e os trechos dele. Cada conteúdo traz `connector_id` e `external_path`.
- **Reindexação agendada** (ADR-0024, migration 0034, `app/knowledge/schedule.py`):
  - O conector aceita `sync_every_hours` (1 a 168; vazio = só manual).
  - Conteúdo de URL aceita `refresh_every_hours` no `POST /url` e em `PUT /contents/{id}/schedule` (vazio desliga; outro tipo de conteúdo dá 422). `POST /contents/{id}/refresh` baixa agora.
  - O poller das suítes reivindica até 10 conectores e 10 URLs vencidos por minuto com `FOR UPDATE SKIP LOCKED` e marca o próximo horário no mesmo commit, antes de trabalhar.
  - A URL só volta a indexar se o sha256 do que veio for diferente do `content_hash` gravado na ingestão. Página fora do ar mantém o que já está indexado.
- **Busca de teste** (`POST /api/v1/knowledge-bases/{id}/search`, `{query, max_results}`): devolve os trechos que o agente receberia, com documento, fonte e score (0 a 1, combinação de similaridade e full-text em português). Base sem conteúdo devolve lista vazia; embedder sem chave ou fora do ar dá 502 com o motivo, porque o `search` do PgVector engole a falha e devolveria vazio.
- **Estratégia de recuperação** (ADR-0017, migration 0028): `retrieval` na base, em `POST` e `PUT` (no `PUT`, ausente mantém o que está gravado). `reranker` é `none` (padrão, a busca de sempre), `mmr` (`mmr_lambda`, de 0 = só diversidade a 1 = só relevância) ou `recency` (`recency_half_life_days` e `recency_weight`). Os rerankers são do Agno (`app/knowledge/rerank.py`). Com reranker, a busca pede ao PgVector o lote maior do `search_limit` e reordena contra a pergunta. A recência lê a data da linha (`return_updated_at`), e reingerir um conteúdo renova a data dele. Falha no reranker devolve a busca sem reordenar. A estratégia vale para todos os agentes que usam a base.
- **HyDE** (ADR-0017): com `hyde: true` e `hyde_model`, obrigatório e da matriz, a busca pede ao modelo uma resposta hipotética e busca com ela no lugar da pergunta (`HyDE` do Agno). O reranker continua ordenando contra a pergunta original. O modelo é sempre explícito, porque sem ele o Agno cairia num da OpenAI. O medidor de `app/evals/judge.py` passou a embrulhar também o `invoke` síncrono, que é o caminho do `HyDE.transform`. Na busca do agente, os tokens viram um `usage_event` do agente, com `run_id` e `user_id` do `RunContext` que o Agno injeta na tool, e com `eval_run_id` dentro da suíte de testes. Na busca de teste, eles só aparecem no resultado. No modo demo o HyDE não roda, e se a chamada falha a busca segue com a pergunta.
- **Comparação na busca de teste**: `POST /api/v1/knowledge-bases/{id}/search/compare`, com o mesmo corpo da busca de teste, devolve `with_strategy` e `without_strategy`. Cada lado traz os trechos, o texto buscado de fato (a resposta hipotética, com HyDE) e os tokens do HyDE. Junto vem a estratégia gravada. A busca de teste simples continua devolvendo a lista de trechos com a estratégia aplicada.
- **Agentes e times** (payload `knowledge: [{base_id, max_results}]`, até 10 bases, `max_results` de 1 a 20, padrão 5): a base precisa existir ao salvar o rascunho (400). A factory cria uma tool `buscar_<slug>` por base, com o nome e a descrição da base na descrição da tool, em vez do `knowledge=` do Agent, que aceita uma base só. A tool devolve JSON com a base e os trechos (documento, fonte, `content_id`, texto); se a busca falha, devolve `erro` e lista vazia para o modelo não responder de cabeça. As instruções ganham um bloco fixo listando as bases e dizendo que o texto devolvido é referência, não instrução. No time, as bases são do líder.
- Remover base usada pela versão vigente ou pelo rascunho de algum agente ou time dá 409 com os nomes.
- Linter: `knowledge-without-guardrail` quando o agente consulta base e não tem guardrails.
- **Custo de embedding**: tabela `embedding_usage` (base, agente quando a busca vem de um run, `ingest` ou `search`, modelo, tokens, custo). Preço por milhão de tokens no código: `voyage-3.5` US$ 0,06, `text-embedding-3-small` US$ 0,02; a faixa gratuita da Voyage não é descontada. Entra em `GET /api/v1/metrics/summary` (`embedding_tokens`, `embedding_cost`, à parte de `total_cost`), em `GET /api/v1/usage/rollup` por agente e nos totais de cada base.
- `MeteredEmbedder` envolve o embedder: conta tokens, guarda as últimas entradas para não pagar duas vezes pelo primeiro trecho e pela pergunta, e transforma vetor vazio (o embedder da OpenAI do Agno devolve `[]` em vez de levantar) em erro. A Voyage recebe `input_type` `document` na ingestão e `query` na busca.
- `DEMO_REPLAY=true` usa um embedder local por hash de palavras, sem chave nem rede. Serve para a demo e os testes, não para produção.

- Postgres com a extensão `vector`: os compose e o testcontainers usam `pgvector/pgvector:pg17` (mesmo Postgres 17, volume existente continua válido). O `PgVector` do Agno roda `CREATE EXTENSION IF NOT EXISTS vector` ao criar a tabela da base, então o usuário do banco precisa poder criar extensão; em Postgres gerenciado (Railway, RDS), habilite `vector` antes.
- Embedder por base, escolhido na criação: `voyage` (padrão, `voyage-3.5`, 1024 dimensões, lê `VOYAGE_API_KEY`) ou `openai` (lê `OPENAI_API_KEY`). A Voyage dá 200M tokens grátis por conta e cobra depois.
- Leitores instalados: PDF (`pypdf`), DOCX (`python-docx`), Markdown, texto, CSV (`aiofiles`), JSON e páginas web (`beautifulsoup4`).
- Settings: `KNOWLEDGE_DEFAULT_EMBEDDER`, `VOYAGE_API_KEY`, `KNOWLEDGE_MAX_UPLOAD_MB` (20), `KNOWLEDGE_ALLOWED_EXTENSIONS` (`pdf,docx,md,txt,csv,json`).
- O SDK da Voyage e os leitores somam ~85 MB de memória quando importados; o limite da API nos compose passou de 256M para 512M.

## Guardrails (ADR-0013)

Regras por agente, no payload versionado (`guardrails`), tudo desligado por padrão. A factory transforma a seção em `pre_hooks` do Agent, do líder do time e de cada membro (com os guardrails da própria versão). Rodam antes de o Agno montar as mensagens: bloquear não custa token de modelo.

| Campo | Regra |
|---|---|
| `pii.mode` = `mask` / `block`, `pii.types` | CPF e CNPJ com dígito verificador, cartão com Luhn, e-mail e telefone brasileiro (com DDD formatado ou +55). `mask` troca o dado por `[CPF removido]` e segue; `block` mascara e bloqueia. Número de pedido de 11 dígitos sem dígito verificador válido passa |
| `prompt_injection`, `injection_extra_terms` | Lista própria em português e inglês, comparada sem acento e sem maiúscula; os termos extras somam à lista |
| `blocked_topics` | Termos que bloqueiam a mensagem (3 a 100 caracteres) |
| `max_input_chars` | Tamanho máximo da mensagem (50 a 100 000) |
| `moderation` | API de moderação da OpenAI; exige `OPENAI_API_KEY` (400 ao salvar sem ela). Uma chamada por mensagem, com o texto saindo da instância |
| `output.pii`, `output.pii_types`, `output.blocked_terms` | Resposta com dado pessoal ou termo proibido. Vira `post_hook` (os guardrails prontos do Agno não funcionam como post_hook) |
| `blocked_message` | O que o usuário vê quando bloqueia |

- Dados pessoais rodam primeiro: o input fica mascarado mesmo quando outra regra bloqueia. O Agno grava o run bloqueado com o input, então a sessão guarda a versão mascarada.
- Bloqueio: run com status `ERROR` e `content` igual à mensagem de bloqueio; no stream, `RunError` com `error_id` (`pii_detected`, `prompt_injection`, `off_topic`, `input_not_allowed`) e `additional_data.rule` com o motivo.
- As regras são `BaseGuardrail` próprias (`app/guardrails/`): os guardrails prontos do Agno só têm padrões dos EUA e lista de injeção em inglês.
- **Saída**: sem stream (integrações REST e MCP), a resposta é trocada pela mensagem de bloqueio, e a mensagem do assistente gravada na sessão também, antes de sair. **Com stream (modo teste, chat), o texto já foi entregue enquanto era gerado**: o run só fica marcado como bloqueado (`output_not_allowed`). O Agno só troca o conteúdo pela mensagem da exceção quando ele está vazio, por isso o hook troca antes de levantar.
- Run barrado vira `status=blocked` em `agent_run`, com `blocked_by` (`pii_detected`, `prompt_injection`, `off_topic`, `input_too_long`, `moderation`) e `block_detail` (tipos de dado ou termo configurado, nunca o valor enviado). O motivo vem de um registro (`BlockLog`) que a factory liga aos guardrails e ao `TrackedAgent`/`TrackedTeam`: o `RunOutput` bloqueado só traz a mensagem. Bloqueio conta em `total_runs` e não em `error_rate`; `GET /api/v1/configs/{id}/metrics` e `/api/v1/metrics/summary` trazem `blocked_runs` e `blocked_by` (contagem por motivo), `/by-agent` traz `blocked_runs` e `/timeseries` traz `blocked_count` por dia.

## Árvore de execução

Com `TRACING_ENABLED=true` (padrão), o AgentOS grava em banco, via OpenTelemetry, os spans de cada run: time, agente, chamada de modelo e tool. A exportação é imediata (`SimpleSpanProcessor`).

- `GET /api/v1/runs/{run_id}/trace` devolve a árvore tipada: `{trace_id, status, duration, total_spans, error_count, tree: [{type, name, duration, status, input, output, error, spans[]}]}`. Num time, a raiz é `TEAM`; abaixo dela vêm os membros (`AGENT`), as chamadas de modelo (`LLM`) e as tools (`TOOL`), inclusive as MCP.
- O trace traz entrada e saída da conversa, então segue a regra do Agno: só o dono do run ou owner. Run sem trace (tracing desligado ou anterior a ele) dá 404.
- A rota é própria porque as `/traces` do Agno ficam fora do OpenAPI que gera os tipos do painel.

## Workflows (ADR-0014)

Workflow é um config com `kind: "workflow"`, criado com `POST /api/v1/configs` e `"kind": "workflow"`. Tem rascunho, publicação, rollback e versões como agente e time. O payload não tem modelo (`model_id` fica `null`; o serviço recusa modelo em workflow e exige em agente e time). A estrutura vai na seção `workflow.steps`, uma árvore de nós com `type`:

- `step`: `name`, `agent_id` **ou** `team_id`, `version_id` opcional (fixa a versão), `on_error` (`stop` para o fluxo, padrão; `continue` passa o erro adiante), `max_retries` (0 a 3) e `review` opcional (ADR-0023): `when` (`before` confirma antes de rodar, `after` aprova a saída), `message` (até 300), `on_reject` (`skip`, `cancel`, padrão, ou `retry`, só com `after`) e `timeout_hours` (1 a 168; vencido, cancela).
- `parallel`: `name` e `branches`, de 2 a 5 etapas `step` que recebem a mesma entrada.
- `condition`: `name`, `rule`, `steps` e `else_steps` opcional.
- `loop`: `name`, `steps`, `max_iterations` (1 a 10) e `until` opcional (regra avaliada na saída da última etapa de cada volta).

Regras (`rule`/`until`) são próprias, sem CEL:
- `kind`: `always`, `contains`, `not_contains`, `starts_with`, `empty` ou `not_empty`;
- `source`: `input` (mensagem original) ou `previous` (saída da etapa anterior, padrão);
- `value`: texto comparado sem maiúsculas.

Validação na escrita:
- nomes de etapa únicos, até 3 níveis de aninhamento e 30 etapas;
- o workflow não termina num `parallel`;
- agentes e times existem, estão publicados e a versão fixada é publicada e deles;
- agente (ou membro de time) com tool de confirmação humana não entra em workflow;
- `review` só em etapa do nível principal: dentro de `condition` o Agno 3.1.8 não pausa, e em `parallel` e `loop` a pausa deixaria o contêiner num estado que o painel não mostra.

Execução (`app/agents/workflow_factory.py`):
- `WorkflowFactory` por request, registrada em `os.workflows` sem restart, como agentes e times. Roda em `POST /workflows/{id}/runs` e exige `workflows:run` (editor e owner); o viewer tem `workflows:read`.
- A árvore vira `Step`, `Parallel`, `Condition` e `Loop` do Agno, montados do zero. Cada etapa ganha uma instância nova de agente ou time, e ramos paralelos não compartilham estado nem conexão MCP. O workflow recebe o `user_id` do run, que o Agno não repassa às etapas sozinho.
- Regras viram funções avaliadas em código nosso. `previous` lê o conteúdo mais profundo da última etapa, não a frase-resumo que o Agno põe depois de um container.
- Etapa com erro ou bloqueio de guardrail levanta `StepFailed`, e assim `on_error`/`max_retries` passam a valer. Com `stop`, o workflow termina com `status=ERROR` e o motivo no `content` (`WorkflowError` no stream), em vez do 500 que o Agno devolveria. Com `continue`, a etapa seguinte roda.
- O run do workflow vai para `agent_run` com status, duração e erro (`TrackedWorkflow`). Cada etapa continua gravada no agente ou time que a executou.
- O `TrackedWorkflow` fixa o `run_id` antes de rodar e o publica numa `ContextVar`. Cada etapa grava esse id em `agent_run.parent_run_id` (migration 0018), inclusive ramos paralelos, cujas tasks herdam o contexto.
- Revisão humana (ADR-0023): `review` vira o `HumanReview` do Agno (`requires_confirmation` ou `requires_output_review`, `on_reject`, `timeout` com `on_timeout=cancel`; `retry` refaz até 3 vezes com o motivo no contexto). O run pausa com `status=PAUSED`, e o `TrackedWorkflow` grava `paused` com um resumo do requisito ativo em `agent_run.pending_steps` (migration 0032): etapa, `when`, mensagem, prazo, tentativas e até 4.000 caracteres da saída na revisão `after`. A decisão é o continue do AgentOS: `GET /workflows/{id}/runs/{run_id}` devolve os `step_requirements`, o painel marca o último com `confirmed` (e `rejection_feedback` na recusa) e manda a lista inteira em `POST /workflows/{id}/runs/{run_id}/continue`, que a substitui. O `TrackedWorkflow` acompanha o continue e atualiza o mesmo `agent_run`: `paused` de novo, ou o desfecho. As etapas depois do continue ficam com o mesmo `parent_run_id`. Na suíte de testes, um caso que chega numa revisão termina em erro.
- Em `GET /api/v1/configs/{id}/runs` de um workflow, cada run traz `steps`, `total_tokens` e `cost`, somados do `usage_event` das etapas filhas. O workflow não grava `usage_event` próprio, então o analytics não conta o consumo duas vezes. Em agente e time esses campos vêm `null`.

## Evals por agente (ADR-0015)

Cada agente, time e workflow tem uma suíte de casos de teste em `/api/v1/configs/{id}/eval-cases`. A tabela é `eval_case` (migration 0019). Os casos ficam fora do payload versionado: um rascunho não consegue afrouxar o próprio teste.

Um caso tem `name` (único na config, até 80 caracteres), `input` (até 4000) e `checks`, de 1 a 5:
- `text`: `kind` = `contains`, `not_contains`, `starts_with`, `empty` ou `not_empty`, e `value`. É a mesma regra dos workflows, comparada sem diferenciar maiúsculas, sobre a resposta. Quantas quiser.
- `tools`: `tools` (1 a 10 nomes, como o agente expõe: `buscar_<slug>` das bases e as tools MCP com prefixo) e `allow_additional` (padrão `true`). No máximo uma por caso.
- `judge`: `criteria` (10 a 1000 caracteres), `mode` (`binary` ou `numeric`) e `threshold` (1 a 10, só no numérico). No máximo uma por caso.
- `blocked` (ADR-0022): o caso passa quando o guardrail barra o run. `rule` opcional exige a regra: `pii_detected`, `prompt_injection`, `off_topic`, `input_too_long`, `moderation` ou `output_not_allowed`. Sempre sozinha no caso, porque um run barrado não tem resposta para checar (422 com outra checagem).
- `steps` (ADR-0022, só workflow): `steps` (1 a 20 nomes de etapa) que precisam ter rodado e `exclusive` (padrão `false`), que reprova se rodar qualquer etapa fora da lista. Só etapas contam, não paralelo, condição ou laço. No máximo uma por caso.

O tipo de config limita as checagens: agente e time aceitam `text`, `tools`, `judge` e `blocked`; workflow aceita `text`, `judge` e `steps`, e caso de workflow não leva `context`, porque o workflow roda uma entrada por vez. Fora disso, 422.

Um caso pode trazer `context`, com até 5 mensagens anteriores (ADR-0016, migration 0026). Na execução, o caso ganha sessão própria (`eval-<uuid>`) e o banco do Agno, que o agente da suíte não recebe do `AgentFactory`. O `setup` do `Case` roda essas mensagens nessa sessão, uma por vez, com 60 s cada, e só a resposta a `input` passa pelas checagens. Os turnos de contexto são runs de teste como os outros: ficam fora das conversas e entram no custo da execução. Todo caso roda com `user_id` de quem disparou a suíte.

`GET /api/v1/configs/{id}/eval-cases/suggestion?run_id=<run>` (ADR-0016) monta um caso a partir de uma conversa real e **não grava nada** (`app/evals/suggest.py`):
- Lê o run em `ai.agno_runs` e os anteriores da mesma sessão.
- A entrada é a mensagem do usuário. O contexto são até 5 mensagens anteriores.
- Checagens: `not_empty` e, se o run chamou tools sem erro, uma de tools com elas, sem repetir. Texto da resposta não vira checagem, porque prenderia o caso à redação daquele dia.
- `judge_criteria` traz um critério de rascunho com a resposta original como referência (até 600 caracteres), para o formulário oferecer.
- Dados pessoais saem mascarados com todos os tipos, mesmo sem guardrail de PII no agente, e `notes` avisa quando houve máscara ou corte de contexto.
- Pede `evals:write` e segue a regra do trace: só quem teve a conversa ou um admin.
- Run de teste, etapa de workflow e run bloqueado dão 422. Run cuja conversa não está mais guardada dá 404.

Salvar usa o `POST` de casos com `source_run_id` (migration 0027), que fica no caso para mostrar de onde veio.

O limite de uma checagem de tools e uma de juiz por caso vem do `Case` do runner de suíte do Agno, que tem um campo para cada. São até 50 casos por config. Run de workflow ainda não vira caso pela sugestão (422). Viewer lê (`evals:read`); editor cria, edita e apaga (`evals:write`).

### Execução da suíte

`POST /api/v1/configs/{id}/eval-runs` com `version_id` opcional cria um `eval_run` (migration 0020) e responde 202. Sem `version_id`, testa o rascunho, se houver; senão, a vigente. A versão precisa ser da própria config. Uma execução por config por vez (409), e a suíte precisa ter ao menos um caso.

No lugar de `version_id`, o pedido aceita `target`: `draft` ou `current` (ADR-0016). Serve a quem não conhece ids de versão, como o CI de um consumidor ou o agendamento. Os dois juntos são recusados (422), assim como `draft` sem rascunho aberto e `current` sem versão publicada. A criação fica em `app/evals/service.py`, comum ao painel, aos tokens de integração e ao agendamento.

O resumo da execução traz:
- `trigger`: `manual`, `integration` ou `schedule` (migration 0023);
- `target`: o apelido usado, quando houver;
- `verdict`: `pending` enquanto roda; `passed` só com a execução concluída e todos os casos aprovados, a mesma regra do gate; `failed` no resto, inclusive com caso não avaliado. É o campo que um pipeline lê para passar ou falhar.

A execução roda em background (`app/evals/runner.py`):
- Cada caso gravado vira um `Case` do `agno.eval.suite` e roda com `arun_cases`, um por vez, com timeout de 120 s.
- Cada caso ganha um agente, time ou workflow novo, montado por `agent_from`, `team_from` ou `load_workflow` e `build_nodes` a partir da versão pedida.
- O `Case` do Agno só aceita agente ou time. O workflow entra em `agent=` pelo adaptador `WorkflowUnderTest` (`app/evals/workflow_case.py`): roda o workflow sem stream e devolve um `RunOutput` com a saída final e as etapas que rodaram em `metadata`. Etapa que parou o workflow vira `WorkflowErrorEvent`, e o caso fica com o motivo. O run do workflow ganha `eval_run_id`, como as etapas, e fica fora das conversas.
- Checagens de texto viram um `Scorer` próprio (`TextScorer`, as mesmas regras dos workflows); as de tools vão para o `expected_tool_calls`.
- O Agno trata o run barrado como erro e só chama o scorer em run completo. Por isso o caso `blocked` leva um scorer que reprova (`respondeu sem bloquear`), e o veredito do bloqueio vem do `BlockLog` do agente ou time do caso, a mesma fonte do `blocked_by`. Bloqueio por orçamento não conta, e o de um turno de contexto é descartado antes do turno avaliado. O resultado traz `rule` e `blocked_by`.
- Checagem de juiz vai para o `criteria` do Agno, com o modelo escolhido em `judge_model` no pedido. O modelo precisa estar na matriz e ter saída estruturada, e é obrigatório quando algum caso tem juiz. Ele é sempre passado ao runner: sem isso o `AgentAsJudgeEval` cairia num modelo da OpenAI. O medidor (`app/evals/judge.py`) embrulha o `ainvoke` da instância e soma os tokens do juiz, gravados num `usage_event` da execução.
- No modo demo (`DEMO_REPLAY`), o juiz não roda: a checagem aparece com `passed: null` e o motivo. Caso só com juiz fica `not_evaluated`, sem rodar o agente.
- No fim, `eval_run.total_tokens` e `eval_run.cost` (migration 0021) somam os `usage_event` da execução: casos e juiz.
- O `on_case_end` grava cada `eval_result` (status `passed`, `failed`, `error` ou `not_evaluated`, checagens com detalhe, resposta, tools chamadas, duração) assim que o caso termina. A execução guarda uma cópia dos casos como estavam.
- Execução presa em `queued`/`running` quando a API reinicia vira `failed` no boot.

Os runs dos casos passam pelo `RunTracking` com a `ContextVar` `current_eval_run`, que grava `agent_run.eval_run_id`, `usage_event.eval_run_id` e, como `user_id`, quem disparou a suíte (o runner do Agno não passa `user_id`). Esses runs ficam fora do histórico de execuções, das aprovações pendentes, das métricas por agente e globais, da série diária, dos bloqueios e do uso no analytics. O rollup de metering (`/api/v1/usage/rollup`) continua contando o custo deles, porque é gasto real.

`GET /api/v1/configs/{id}/eval-runs` lista as 20 últimas; `GET .../eval-runs/{run_id}` traz os resultados por caso.

No `GET /api/v1/metrics/summary`, `eval_tokens` e `eval_cost` trazem o consumo das suítes no período, fora do `total_cost` das conversas.

### Comparação e gate de publicação

`GET /api/v1/configs/{id}/eval-runs/compare?base=<run>&target=<run>` compara duas execuções caso a caso, pelo id do caso, ou pelo nome quando o caso foi apagado. Cada caso sai como `regression` (passava e deixou de passar), `fix`, `same`, `new` ou `removed`, com a contagem de regressões e correções. O uso típico é a vigente como base e o rascunho como alvo.

O gate é a flag `agent_config.require_passing_evals` (migration 0022), fora da versão, como os casos:
- `PUT /api/v1/configs/{id}/eval-settings` liga e desliga.
- `GET` devolve a flag, a última execução no rascunho atual, se publicar está liberado (`can_publish`) e o motivo.
- Com a flag ligada, `POST /api/v1/configs/{id}/publish` responde 409 até que a última execução no `draft_version_id` atual esteja concluída com todos os casos aprovados. Caso não avaliado não conta como aprovado.
- Como cada rascunho salvo é uma versão nova, editar o rascunho invalida o resultado anterior sem precisar de hash.
- Rollback não passa pelo gate: voltar para uma versão já publicada segue livre, porque é a saída de emergência.

### Agendamento

`/api/v1/configs/{id}/eval-schedule` (ADR-0016, migration 0025) guarda um agendamento por config: `GET` lê, `PUT` cria ou troca e `DELETE` apaga. Ler pede `evals:read`; gravar, `evals:write`. O corpo é `{cron_expr, timezone, target, judge_model, enabled}`:
- `timezone` padrão `America/Sao_Paulo` e `target` padrão `current`, para o agendamento seguir a vigente depois de cada publicação.
- O cron tem 5 campos e é validado com `agno.scheduler.cron`. Cron vazio é recusado. O intervalo mínimo entre horários seguidos é 1 hora, conferido nos próximos 48 horários.
- A gravação já recusa o que o horário recusaria: caso com juiz sem `judge_model` ou modelo sem saída estruturada. Desligado, `next_run_at` fica nulo.

O poller fica em `app/evals/scheduler.py`:
- Um laço no lifespan do app externo acorda a cada 60 s. O Starlette não roda o lifespan do AgentOS montado, por isso o laço fica no app de fora.
- Ele reivindica os vencidos com `SELECT … FOR UPDATE SKIP LOCKED` e cria a execução pelo `create_run`, com `trigger: schedule` e `started_by: agendamento`. Grava o próximo horário e a execução no mesmo commit, com a linha ainda travada. Com duas réplicas, a segunda pula a linha travada.
- O próximo horário é calculado a partir de agora. Se a API ficou fora do ar, a execução vencida roda uma vez só na volta.
- Horário recusado (execução em andamento, suíte sem casos) não para o agendamento: o motivo vai para `last_error` e o próximo horário segue.
- Desligado com `EVAL_SCHEDULER_ENABLED=false` e sempre desligado no modo demo. Os testes desligam o laço e chamam o `poll_once` direto.

### Rodar a suíte no CI de quem consome o agente

Com um token de integração emitido com `eval_ids`, o pipeline dispara a suíte na vigente (ou no rascunho, com `target: draft`) e lê o `verdict` até sair de `pending`. Exemplo de passo de CI, em shell:

```bash
API=https://api.suaempresa.com
AGENTE=<config_id do agente>
RUN=$(curl -sf -X POST "$API/api/v1/configs/$AGENTE/eval-runs" \
  -H "Authorization: Bearer $AUTOMATA_TOKEN" -H "Content-Type: application/json" \
  -d '{"target": "current", "judge_model": "gpt-4o-mini"}' | jq -r .id)
for _ in $(seq 1 60); do
  VERDICT=$(curl -sf "$API/api/v1/configs/$AGENTE/eval-runs/$RUN" \
    -H "Authorization: Bearer $AUTOMATA_TOKEN" | jq -r .verdict)
  [ "$VERDICT" != "pending" ] && break
  sleep 10
done
echo "suíte: $VERDICT"
[ "$VERDICT" = "passed" ]
```

- `judge_model` só é preciso quando algum caso tem juiz.
- Execução já em andamento responde 409: o pipeline pode esperar e tentar de novo.
- O token fica em um segredo do CI (`AUTOMATA_TOKEN`) e vale até 90 dias. Revogar no painel corta na hora.

### Webhook de aviso

Cada agendamento pode ter um webhook (ADR-0018, migration 0029), em `/api/v1/configs/{id}/eval-schedule/webhook`, com `evals:write`:
- `PUT {url}` cadastra ou troca e devolve o `secret` **uma vez só**. A URL e o segredo ficam cifrados juntos com `MCP_SECRETS_KEY` (sem a chave, 422), porque URL de Slack e Teams carrega token. O agendamento mostra só `webhook_host`.
- `DELETE` remove. `POST /test` manda um `suite.test`, numa tentativa só, e devolve o resultado.
- Agendamento sem webhook dá 404 no teste, e webhook sem agendamento também dá 404.

A saída passa pelo `check_url` dos servidores MCP, no cadastro e a cada envio: só https, nada que resolva para IP interno, salvo hosts em `MCP_ALLOWED_HOSTS`. Redirect não é seguido.

Cada envio (`app/evals/webhook.py`) leva:
- os headers `X-Automata-Event` e `X-Automata-Signature: sha256=<HMAC-SHA256 do corpo com o segredo>`;
- corpo JSON com `event`, `at`, dados do evento e o resumo em `text` (Slack, Teams) e `content` (Discord), que funciona colado num canal sem adaptador.

Na entrega, são até 3 tentativas, com timeout de 10 s e espera de 1 s e 5 s. Uma resposta 4xx não é repetida. O resultado fica em `webhook_last_status` e `webhook_last_at`.

Depois de cada execução agendada, `app/evals/notify.py` compara com a agendada anterior (concluída ou com falha) e só avisa quando o estado muda:
- verde para caso que passava e falhou: `suite.regressed`, com `regressions`;
- verde para falha sem regressão, ou primeira agendada já falhando: `suite.failing`;
- falhando para verde: `suite.recovered`.

Estado igual não avisa. Execução manual ou por token não avisa. O corpo traz `config_id`, `config_name`, `run_id`, `previous_run_id`, `passed`, `total` e `regressions`. O poller roda o aviso depois da execução, e falha no aviso nunca afeta a suíte.

### Estado da suíte

`GET /api/v1/eval-status` (`evals:read`) devolve, para cada config que já rodou a suíte, o estado pela execução mais recente (`app/evals/compare.py`):
- `running` enquanto ela roda;
- `passing` com todos os casos aprovados;
- `failing` no resto;
- `regressed` quando a execução mais recente é agendada e perdeu caso que passava na agendada anterior.

Cada item traz `regressions`, `previous_run_id` e o resumo da última execução. O painel usa isso na lista de agentes e times e abre a comparação com `base=previous_run_id`. Regressão só é calculada entre execuções agendadas, que têm a mesma origem e o mesmo alvo. Entre uma manual no rascunho e uma agendada na vigente, a diferença não diz nada. A comparação caso a caso saiu do router para o mesmo módulo e serve às duas telas.

