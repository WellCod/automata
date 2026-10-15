# ADR-0010 — Servidores MCP externos como cadastro operacional, com segredo cifrado e só HTTP

**Status:** Aceito
**Data:** 2026-10-15

## Contexto

Até aqui o campo `tools` do config era uma lista de strings que nunca chegava ao `Agent`: a factory montava o agente sem ferramenta nenhuma. Para o agente agir sobre sistemas do cliente (CRM, ERP, base de conhecimento), o caminho padrão é consumir servidores MCP com `MCPTools`, a direção inversa da superfície descrita no ADR-0009.

Verificado no Agno 2.8.7 instalado:

- `MCPTools(url=..., transport="streamable-http", tool_name_prefix=..., include_tools=..., refresh_connection=..., header_provider=...)`; `requires_confirmation_tools` passa por `**kwargs`.
- Instanciado dentro da factory por request, o `Agent` conecta no início do `arun` e fecha no fim. O lifespan do AgentOS só gerencia MCP de componentes estáticos, o que não é o nosso caso.
- `connect()` engole a exceção e só loga. Um servidor fora do ar faz o agente rodar **sem as tools**, sem erro visível.
- Transporte `stdio` executa um comando no host da API. SSE está depreciado no próprio Agno.

## Decisão

Servidor MCP é uma entidade própria (`mcp_server`), **não versionada**, referenciada pelos configs de agente. Só transporte `streamable-http`. Valores de header são segredos cifrados em repouso com Fernet (`MCP_SECRETS_KEY`) e nunca saem da API. A factory conecta cada servidor explicitamente e **falha o run** se algum não conectar.

O config de agente passa ao `schema_version: 2`, com `mcp_servers: [{server_id, tools, require_confirmation}]`, em que `tools` é a lista de tools liberadas (nula = todas).

## Alternativas descartadas

**Servidor MCP dentro do payload versionado do agente.** URL e credencial mudam por motivo operacional (rotação de token, troca de ambiente), não por mudança de comportamento do agente. Versionar junto obrigaria a republicar todo agente a cada rotação, e espalharia o segredo por N versões imutáveis.

**Permitir `stdio`.** É execução de comando arbitrário no host da API, configurável pelo painel. Num produto single-tenant com papéis (ADR-0003, ADR-0005), um editor viraria quem roda processos no servidor. A allowlist de executáveis do Agno (`npx`, `uvx`, `docker`…) não reduz o risco: `npx` roda qualquer pacote.

**Segredo em texto no banco.** Backup e réplica de leitura passariam a carregar credenciais de sistemas do cliente.

**Vault externo (AWS Secrets Manager, Vault).** Resposta melhor em escala, mas impõe uma dependência de infraestrutura a cada instância (ADR-0003). Fica como evolução: a interface de leitura do segredo é uma função só.

**Seguir o comportamento padrão de conexão.** Agente que responde sem as ferramentas que deveria usar inventa a resposta. Falha visível é preferível a resposta plausível e errada.

## Consequências

- Tabela `mcp_server`: nome, slug (vira `tool_name_prefix`), URL, timeout, headers cifrados, retrato das tools descobertas (nome, descrição, schema) com a data da última descoberta, e auditoria de quem alterou.
- `MCP_SECRETS_KEY` é obrigatória quando houver servidor com header. Perder a chave obriga a recadastrar os segredos; rotacionar exige re-cifrar (comando próprio).
- Proteção de SSRF: a URL é resolvida e recusada se cair em rede privada, loopback ou link-local (inclui o endpoint de metadados de cloud), a menos que o host esteja em `MCP_ALLOWED_HOSTS`. A checagem roda ao salvar e ao conectar, porque DNS muda.
- Editar a URL ou o segredo de um servidor afeta na hora todo agente que o usa. É o comportamento desejado para rotação, mas o painel precisa mostrar quais agentes dependem do servidor antes de salvar.
- Prefixo por servidor evita colisão de nome de tool entre servidores, que o `MultiMCPTools` não resolve.
- Migração do payload v1→v2 fica em código (`schema_version`, ADR-0002). O `tools: list[str]` antigo nunca teve efeito e é descartado.
- Cada run abre e fecha as conexões. Custa latência por request; em troca não há conexão compartilhada entre requests concorrentes (o `deep_copy` do Agno compartilha a instância de `MCPTools`).

## O que me faria reverter

- Latência de conexão por run virar gargalo medido: passar a um pool de sessões MCP por servidor, com health check.
- Cliente exigir servidor MCP local (stdio) em instância própria e isolada: liberar por variável de ambiente da instância, nunca pelo painel.
- Mais de um cliente pedir vault externo: trocar a implementação de leitura de segredo.
