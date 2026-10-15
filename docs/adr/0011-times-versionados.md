# ADR-0011 — Times multi-agente na mesma tabela de configs, com membros por referência

**Status:** Aceito
**Data:** 2026-10-15

## Contexto

O próximo passo do produto é compor agentes: um líder que delega a especialistas. O Agno 2.8.7 tem `Team` com quatro modos (`coordinate`, `route`, `broadcast`, `tasks` — não existe `collaborate`), `TeamFactory` equivalente ao `AgentFactory`, rotas `/teams/*` e scopes `teams:<id>:run`, e emite no mesmo stream os eventos dos membros.

O Agno também persiste times e versões por conta própria (`Team.save`, `/components`), mas isso é o Studio que o ADR-0002 recusou como fonte da verdade. Nas mesmas rotas, o Agno sempre carrega o membro na versão mais recente (há um TODO no código dele).

## Decisão

Time é um config com `kind = "team"` nas tabelas `agent_config` e `agent_config_version` que já existem, e reaproveita rascunho, publicação, rollback, histórico e métricas. O payload de time guarda modo, modelo e instruções do líder, flags de delegação, servidores MCP do líder e a lista de membros por referência a agentes publicados.

Por padrão, o membro segue a versão **vigente** do agente. Opcionalmente o membro pode ser fixado numa versão. Na primeira versão, membro é só agente: time dentro de time fica de fora.

## Alternativas descartadas

**Tabelas próprias de time.** Duplicaria serviço, repositório, rotas, tela de versões, diff, rollback, runs e métricas, que são a maior parte do código de config. A diferença real está só no payload e na factory.

**Persistência nativa do Agno (`Team.save`, `/components`).** Recusada pelo ADR-0002. Além disso, ela não fixa a versão do membro.

**Membro sempre fixado em versão.** Dá reprodutibilidade, mas cada publicação de agente obrigaria a republicar todo time que o usa. Na prática os times ficariam com membros desatualizados sem ninguém perceber. Fixar fica como opção, para o time que precisa de estabilidade.

**Time aninhado desde já.** Exige detecção de ciclo na escrita e na resolução, e multiplica o custo por run sem caso de uso concreto.

## Consequências

- A coluna `kind` entra em `agent_config` com default `"agent"`. Listagens e o registro no AgentOS filtram por `kind`. O nome `agent_config` passa a ser impreciso: aceito para não renomear a tabela com dados.
- O payload ganha uma seção opcional `team` (modo, membros, limite de iterações, compartilhar interações). Modelo, instruções e servidores MCP do payload passam a ser os do líder. Optei por isso em vez de uma união discriminada por `kind`: o painel e os tipos gerados seguem com um formato só. A coerência entre `kind` e a seção `team` é validada no serviço. Validação na escrita: membros existem, são agentes, estão publicados, não se repetem, a versão fixada é publicada e do próprio agente, e o time tem de 1 a 20 membros. A descrição do agente já é obrigatória e vira o `role` do membro.
- **A descrição do membro é o contrato de roteamento do líder**, como a do agente é para o cliente MCP (ADR-0009). Descrição vaga é falha de delegação. O linter ganha regras para isso.
- Publicar um agente muda o comportamento de todo time que o usa sem fixação. O painel mostra, no agente, os times que dependem dele.
- `agent_run` e `usage_event` passam a registrar runs de time, com o consumo agregado (o `RunOutput` do time já soma os membros). O detalhe por membro vem da árvore de execução, não do `agent_run`.
- Só o caminho assíncrono do `Team` suporta MCP no Agno, e é o que o AgentOS usa.

## O que me faria reverter

- Caso concreto de time dentro de time: liberar com detecção de ciclo e limite de profundidade.
- Times e agentes divergirem a ponto de a seção `team` encher serviço e tela de `if kind`: separar payloads ou tabelas.
- O Agno passar a fixar versão de membro e a expor persistência auto-hospedável e white-label: reavaliar junto com o ADR-0002.
