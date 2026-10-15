# automata — api

API em Python sobre o Agno AgentOS.

## Dependências principais

| Pacote | Versão pinada | Licença |
|--------|--------------|---------|
| agno[os] | 2.8.7 | Apache 2.0 |
| psycopg[binary] | ≥3.2 | LGPL-3.0 |
| alembic | ≥1.14 | MIT |
| pydantic-settings | ≥2.7 | MIT |

A licença do Agno na versão 2.8.7 é **Apache 2.0**, confirmada em `github.com/agno-agi/agno/blob/main/LICENSE`. ADR-0007 registrava incerteza entre MPL-2.0 e Apache-2.0 — resolvida: é Apache 2.0, compatível com AGPL-3.0 para fins de distribuição.

## Rodando local

Para desenvolvimento, a API roda em Docker junto com o banco. A partir da raiz do repositório:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

A API sobe em `http://localhost:8000` com hot-reload ativo. As migrations rodam automaticamente no boot via `alembic upgrade head`.

Para rodar isolado (sem Docker), com banco já acessível via `DATABASE_URL`:

```bash
cd api
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

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
- `.github/workflows/evals-nightly.yml` — workflow agendado

## Metering

`GET /api/v1/usage/rollup?period=YYYYMM&agent_id=<uuid>` — retorna consumo agregado por agente no período.

O rollup agrega tokens e custo por `(agent_config_id, period)`. Campos: `run_count`, `input_tokens`, `output_tokens`, `total_tokens`, `cost`.

## Runtime de agentes

- **Factory por request** (`app/agents/factory.py`): lê a versão vigente (ou a `version_id` do modo teste, que precisa ser do mesmo agente — outra versão dá 400) e monta o `Agent`. Leitura do banco fora do event loop.
- **Registro sem restart** (`app/agents/registry.py`): a lista de agentes do AgentOS é sincronizada com os configs publicados no boot, logo após cada publicação e, com TTL de 5 s, antes de requests a `/agents`, `/teams`, `/mcp` e `/config` — o que cobre publicações feitas em outro worker.
- **Registro de execução** (`app/agents/tracking.py`): o `TrackedAgent` envolve `arun` e `acontinue_run` e grava em `agent_run` o desfecho real — `success`, `error`, `cancelled` ou `paused` — com duração e erro, e em `usage_event` os tokens e o custo, na mesma transação. Run pausado e retomado atualiza a mesma linha (por `run_id`). Post-hooks do Agno não serviam: só rodam quando o run termina bem. Runs com `background=true` não são registrados.
- **Tools MCP** (ADR-0010): o payload v2 traz `mcp_servers: [{server_id, tools, require_confirmation}]`, em que `tools: null` libera todas as tools do servidor. A factory monta um `MCPTools` por servidor, com prefixo pelo slug (`crm_buscar_cliente`) e só as tools liberadas. O `TrackedAgent` conecta todos **antes** do run, na mesma task, e registra as conexões para o próprio Agno fechá-las no fim. Se um servidor não conecta, o run termina com `status=ERROR` (ou `RunError` no stream) dizendo qual servidor falhou, e fica gravado como `error`. O agente nunca responde sem as tools que deveria ter.
- **Validação na escrita**: o servidor precisa existir, e as tools liberadas e as que pedem confirmação precisam constar no retrato descoberto, quando ele existe. Confirmação só vale para tool liberada (422).
- **Payload v1** (`tools: list[str]`, que nunca teve efeito) é convertido para v2 na leitura. Versões antigas seguem legíveis e o próximo rascunho já sai em v2.
- **Capabilities**: `extended_thinking` liga `thinking` no Claude (budget de 4096 tokens). Visão depende só do modelo; `structured_output` ainda não tem efeito porque o config não guarda `output_schema`.

## Scopes JWT

Autenticação por JWT assimétrico RS256. O backend emite o token (via `app.auth.issue_token`), o AgentOS verifica usando a chave pública de `JWT_PUBLIC_KEY`. `user_isolation=True` ativo — cada usuário só enxerga suas próprias sessões e memórias.

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
| `metrics:read` | `GET /api/v1/configs/{id}/runs`, `GET /api/v1/configs/{id}/metrics`, `GET /api/v1/metrics/*`, `GET /api/v1/usage/rollup` |
| `mcp_servers:read` | `GET /api/v1/mcp-servers`, `GET /api/v1/mcp-servers/{id}` |
| `mcp_servers:write` | `POST`, `PUT` e `DELETE` em `/api/v1/mcp-servers` — só owner (`agent_os:admin`) |
| `agent_os:admin` | `POST /api/v1/auth/users` |

`POST /api/v1/auth/login` e `GET /health` são públicos.

### Papéis

Definidos em `ROLE_SCOPES` (`app/schemas/user.py`) e gravados no token no login. Mudança de papel vale a partir do próximo login.

| Papel | Scopes |
|---|---|
| `owner` | `agent_os:admin` |
| `editor` | tudo do viewer + `agents:run`, `sessions:write`, `configs:write`, `configs:publish` |
| `viewer` | `agents:read`, `sessions:read`, `traces:read`, `configs:read`, `metrics:read`, `mcp_servers:read` |

### Chaves

A chave privada (`JWT_PRIVATE_KEY`) existe só no processo da API, que emite os tokens. O painel recebe apenas `JWT_PUBLIC_KEY` para verificar o cookie no proxy (ADR-0005). Os testes geram um par em memória.

### Rate limit do login

5 tentativas por minuto por e-mail e 20 por IP. O IP vem de `X-Forwarded-For` só quando a conexão chega de um proxy listado em `TRUSTED_PROXIES` (IPs ou CIDRs); o header é lido da direita para a esquerda e vale o primeiro hop fora da lista. Sem `TRUSTED_PROXIES`, vale o IP da conexão. O BFF repassa o IP do cliente na rota `/api/auth/login` e descarta cabeçalhos de encaminhamento vindos do browser no proxy genérico, que também recusa `v1/auth/login`.

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
