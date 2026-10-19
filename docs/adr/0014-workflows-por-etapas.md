# ADR-0014 — Workflows por etapas sobre os agentes e times publicados, com regras próprias no lugar de CEL

**Status:** Aceito
**Data:** 2026-10-19

## Contexto

Um time (ADR-0011) delega por decisão do líder: o modelo escolhe quem chamar e em que ordem. Há processos em que a ordem é fixa e precisa ser auditável — triagem, consulta ao CRM e redação da resposta, sempre nessa sequência; duas análises em paralelo e uma consolidação; uma revisão que só roda quando a resposta menciona reembolso. Para isso o Agno tem Workflows.

Verificado no Agno 2.8.7 instalado:

- Primitivas `Step` (um agente, time ou função), `Steps`, `Parallel`, `Condition` (com `else_steps`), `Loop` (`max_iterations`, `end_condition`) e `Router`. `WorkflowFactory` igual à de agente e time, rotas `/workflows/*`, scopes `workflows:<id>:run` e tool `run_workflow` no `/mcp`. O AgentOS lê `os.workflows` a cada request.
- Cada etapa recebe como entrada só a saída da etapa anterior; a primeira recebe a mensagem do usuário. Depois de um `Parallel`, a etapa seguinte recebe as saídas de todos os ramos, cada uma sob o nome do ramo.
- Condições, fim de loop e roteador aceitam função, booleano ou expressão CEL. O pacote CEL (`cel-python`) **não está instalado**, e sem ele toda expressão vira `False` em silêncio. Função não é serializável.
- Etapa cujo agente falha não para o workflow: o Agno devolve o erro como conteúdo e a etapa seguinte recebe a mensagem de erro como entrada. `on_error` só age em exceção.
- As etapas rodam com `user_id` da instância do `Workflow`, não do run: sem ajuste, todo run de etapa seria gravado como anônimo.
- A mesma instância de agente em dois ramos paralelos compartilha estado, inclusive as conexões MCP.
- Pausa humana: só nas etapas de topo, não existe dentro de `Parallel`, e o `continue` reconstrói o workflow pela factory, então uma publicação entre a pausa e o continue muda a estrutura sob o run pausado.

## Decisão

Workflow é um config com `kind = "workflow"` nas tabelas existentes, como o time, e reaproveita rascunho, publicação, rollback, versões, execuções e métricas. O payload ganha a seção `workflow`, uma árvore de nós: `step` (agente ou time publicado, com versão vigente ou fixada), `parallel`, `condition` e `loop`.

Condições e fim de loop usam **regras próprias**, avaliadas em código nosso e montadas por formulário no painel: `sempre`, `contém`, `não contém`, `começa com` e `vazio`, sobre a mensagem original ou a saída da etapa anterior, sem diferença de maiúsculas. Não há CEL.

Etapa com erro **para o workflow** por padrão. Cada etapa pode ser marcada para seguir mesmo com erro e ter até 3 tentativas.

A factory monta tudo do zero a cada request, com uma instância nova de agente ou time por etapa, e passa o `user_id` do run.

Sem pausa humana na primeira versão.

## Alternativas descartadas

**CEL.** Seria só adicionar `agno[cel]`, mas a expressão é linguagem de programação dentro de um painel para quem não programa, e o erro de digitação vira `False` sem aviso, o que pula etapas em produção sem ninguém perceber. As regras próprias cobrem os casos que apareceram (a resposta fala de X, a triagem disse "urgente"), são validadas na escrita e mostram o motivo na árvore de execução.

**Router por modelo.** Escolher a etapa com uma chamada de LLM é o que o time em modo `route` já faz. No workflow a escolha precisa ser determinística e explicável.

**`Workflow.from_dict` com o Registry do Agno.** O Registry só aceita instâncias, não factories, e o `deep_copy` que ele usa recria agentes pelo construtor e perde os atributos de rastreamento (`automata_config_id`), além de deixar etapas paralelas com a mesma instância.

**Seguir em caso de erro, como o Agno faz.** A etapa seguinte receberia "servidor MCP indisponível" como se fosse a resposta da anterior e produziria um resultado plausível e errado. Parar é o padrão seguro; seguir fica como opção explícita por etapa.

**Pausa humana já.** Funciona só em parte da árvore e exige fixar a versão entre a pausa e o continue. Fica para quando houver caso de uso, com essas duas restrições resolvidas.

## Consequências

- `kind = "workflow"` e `model_id` passa a ser opcional no payload; o serviço exige modelo em agente e time e o recusa em workflow.
- Validação na escrita:
  - nomes de etapa únicos (o Agno indexa saídas e métricas por nome);
  - agentes e times existem e estão publicados;
  - a versão fixada é publicada e do próprio componente;
  - profundidade de aninhamento até 3 e no máximo 30 etapas;
  - `loop` com 1 a 10 iterações;
  - o workflow não termina num `parallel` (a saída final seria só o último ramo; uma etapa depois consolida);
  - agente com tool que exige confirmação humana não entra em workflow.
- Erro de etapa: o agente da etapa levanta exceção quando o run termina em erro ou bloqueio de guardrail, e o `on_error` do Agno (`fail` ou `skip`) e o `max_retries` passam a valer. Dentro de `parallel` o erro de um ramo não derruba os outros.
- Rastreamento: o run do workflow vai para `agent_run` com o id do workflow, status e duração. Cada etapa continua gravada no agente ou time que a executou, com `parent_run_id` apontando para o run do workflow. O consumo do workflow é a soma das etapas, sem contar duas vezes no analytics.
- Registro sem restart em `os.workflows`, como agentes e times. Papéis: viewer ganha `workflows:read`, editor `workflows:run`.
- Só o caminho assíncrono (`arun`), como em time; MCP dentro de etapa conecta no run do agente.

## O que me faria reverter

- Pedido concreto de condição que as regras não expressam: liberar CEL como modo avançado, com validação de nomes de variável na escrita e erro visível em vez de `False`.
- Caso de uso de aprovação humana no meio do fluxo: implementar pausa em etapa de topo, com a versão do workflow gravada no run e usada no continue.
- O Agno passar a aceitar factories no Registry e preservar atributos no `deep_copy`: reavaliar a montagem pela serialização nativa.
