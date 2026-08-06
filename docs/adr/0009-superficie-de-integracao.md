# ADR-0009 — Superfície de integração: MCP server mode e REST, com descrição de agente como contrato

**Status:** Proposto — não confirmado
**Data:** 2026-08-06

## Contexto

O painel resolve a configuração por humano. O valor operacional, porém, aparece quando outros sistemas invocam os agentes: uma ferramenta de atendimento chamando o agente de triagem, um backend chamando o de cobrança, um assistente de IA de terceiro usando um agente nosso como ferramenta.

O AgentOS expõe quatro superfícies, verificadas na documentação:

- **REST API** — endpoints HTTP tradicionais, sempre disponíveis
- **MCP server mode** — habilitado com `enable_mcp_server=True`, publica um endpoint `/mcp` que implementa o Model Context Protocol. Torna agentes, teams e workflows chamáveis como tools por qualquer cliente MCP. Opera de forma independente das outras interfaces, simultaneamente à REST
- **A2A** — protocolo agente-a-agente, para interoperar com agentes construídos em outros stacks
- **AG-UI** — streaming de eventos estruturados para frontend

Vale distinguir de `MCPTools`, que é a direção inversa: nossos agentes **consumindo** tools de servidores MCP externos. As duas coexistem, e a documentação descreve o AgentOS como hub de integração exatamente por isso.

## Decisão proposta

Habilitar **REST** e **MCP server mode**. A2A e AG-UI ficam fora do escopo inicial.

Consequência tratada como requisito, não como detalhe: **nome e descrição de agente passam a ser contrato de máquina**, com validação obrigatória.

## Alternativas descartadas

**Só REST.** Funciona, mas obriga cada consumidor de IA a escrever integração sob medida. MCP server mode entrega descoberta e invocação padronizadas sem código adicional do nosso lado — é ganho grande por uma flag.

**Habilitar A2A agora.** A2A serve delegação entre agentes de frameworks diferentes. Não há esse caso de uso hoje. Habilitar superfície sem consumidor é aumentar área de ataque sem retorno. É reversível a qualquer momento.

**Habilitar AG-UI.** Nosso frontend passa pelo BFF e consome a REST — ver ADR-0005. AG-UI resolveria streaming direto ao browser, o que contraria a decisão de não expor o runtime ao client.

**Endpoint proprietário de integração.** Reinventaria descoberta e schema de tool que o MCP já padroniza.

## Consequências

**Descrição de agente vira interface funcional.** Em MCP server mode, o modelo do cliente lê nome e descrição para decidir *quando* chamar o agente. Descrição vaga não é problema estético, é falha de roteamento — o agente é chamado na situação errada, ou não é chamado. Portanto:

- Descrição passa a ser campo obrigatório, com mínimo de conteúdo validado na escrita
- A validação deve exigir que a descrição diga em que situação usar o agente, não apenas o que ele é
- Renomear ou reescrever a descrição de um agente publicado é mudança de contrato, não edição cosmética. Deve gerar nova versão

**Controle de acesso já está resolvido.** Os scopes do AgentOS têm granularidade por agente, no formato `agents:<id>:run` — ver ADR-0005. Cada ferramenta consumidora recebe token limitado aos agentes que pode invocar. Não exige código novo, apenas política de emissão de token. Essa política precisa estar documentada e ser visível no painel: quem consegue chamar o quê.

**Edição pelo painel afeta consumidores imediatamente.** Como a configuração é lida por request pela factory (ADR-0002 e ADR-0006), publicar uma versão muda o comportamento de todas as ferramentas integradas sem redeploy. É o comportamento desejado, mas eleva o risco de uma edição ruim. Reforça a necessidade de rollback em um clique e de modo teste antes de publicar.

**Restrição operacional verificada, e ela contradiz o setup inicial:** quando há `MCPTools` dentro do AgentOS, `reload=True` não deve ser usado. Hot reload quebra as conexões MCP durante o ciclo de vida do FastAPI. O `docker-compose.yml` precisa desabilitar reload quando MCP estiver ativo, ou separar perfis de desenvolvimento.

**Refresh de conexão MCP não é automático.** A documentação afirma que o AgentOS não trata reconexão. Se a conexão a um servidor MCP externo cair, o comportamento precisa ser verificado antes de depender disso em produção. Item aberto.

**Superfície de ataque cresce.** Um endpoint a mais, exposto a clientes que não controlamos. Autorização por scope é obrigatória em `/mcp`, não opcional — confirmar que o modo MCP respeita a configuração de autorização antes de expor publicamente.

## Pendências antes de aceitar

- Confirmar que `/mcp` está sujeito à mesma verificação de JWT e scopes da REST. Se não estiver, MCP server mode não é habilitável em produção como está.
- Verificar comportamento de reconexão de `MCPTools`.
- Definir a política de emissão de token por ferramenta consumidora e onde ela é administrada no painel.

## O que me faria reverter

Se `/mcp` não respeitar o mesmo controle de autorização da REST, desabilitar MCP server mode até que respeite. Conveniência de integração não compensa endpoint sem controle de acesso.

Se um consumidor exigir delegação entre agentes de frameworks distintos, habilitar A2A — decisão aditiva, não substitui nada.

Sinal na direção oposta: se as descrições de agente começarem a ser escritas para agradar o roteamento do modelo cliente em vez de descrever o agente, o acoplamento se inverteu e vale reavaliar se a exposição via MCP deve ser um subconjunto curado, e não o catálogo inteiro.
