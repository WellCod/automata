# ADR-0023 — Revisão humana numa etapa do workflow, antes de rodar ou depois da saída

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-10-21

## Contexto

O workflow (ADR-0014) roda do começo ao fim sem parar. A única pausa humana do Automata é a confirmação de tool sensível (Fase 12): o agente para antes de chamar a tool, e a página Aprovações libera ou recusa.

Isso não cobre o caso mais comum de fluxo com gente no meio, que é **aprovar o resultado de uma etapa antes da próxima**. Exemplos:

- o financeiro aprova o valor do reembolso que a análise calculou antes de a resposta ao cliente sair;
- o jurídico confere a minuta antes do envio;
- o supervisor libera a etapa que abre chamado no sistema de outro time.

Hoje isso só se faz quebrando o fluxo em dois workflows, com alguém copiando a saída de um para o outro.

Verificado no Agno 3.1.8 instalado:

- `Step(human_review=HumanReview(...))`. Com `requires_confirmation`, a etapa pausa **antes** de rodar. Com `requires_output_review`, a etapa roda e pausa **depois**, com a saída disponível em `StepRequirement.step_output`.
- `on_reject`:
  - `skip` pula a etapa;
  - `cancel` encerra o workflow;
  - `retry`, só na revisão da saída, roda a etapa de novo com o motivo da recusa (`rejection_feedback`) no contexto, até `max_retries`.
- `timeout` com `on_timeout` (padrão `cancel`) vence a pausa parada.
- O run pausado sai com `status=paused` e `step_requirements`. No stream, isso vem no `WorkflowPausedEvent`.
- O AgentOS expõe `POST /workflows/{id}/runs/{run_id}/continue` com `step_requirements` em JSON. A lista enviada **substitui** a do run, e o requisito ativo é o último. Ler o run por `GET /workflows/{id}/runs/{run_id}` devolve os requisitos para o painel marcar `confirmed`.
- O `continue` já passa pelo mesmo controle de acesso do run (`workflows:run`, dono da sessão) e pelo gate de aprovação do AgentOS.

No código atual:

- O factory já põe `HumanReview(on_error=...)` em toda etapa, só para o tratamento de erro.
- O `TrackedWorkflow` grava o run como `paused` quando o stream termina em `WorkflowPaused`. Ele não guarda o que está pendente e não acompanha o `continue`: o run ficaria `paused` para sempre em `agent_run`.
- A página Aprovações lista só runs de agente com `pending_tools`.

## Decisão

**Revisão por etapa, versionada no payload.** A etapa do workflow ganha `review`, opcional:

- `when`: `before` (confirma antes de rodar) ou `after` (aprova a saída antes da próxima etapa);
- `message`: o que o revisor precisa conferir, até 300 caracteres;
- `on_reject`: `skip`, `cancel` ou `retry`. `retry` só vale com `after`, e a etapa roda de novo com o motivo da recusa, até 3 vezes;
- `timeout_hours`: de 1 a 168, vazio = sem prazo. Vencido, o workflow é cancelado.

**Só em etapa do nível principal do workflow.** Verificado no 3.1.8: a revisão de uma etapa dentro de condição não pausa, e o fluxo segue como se ela não existisse. Uma pausa num ramo paralelo ou numa volta de laço deixaria o resto do contêiner num estado que o painel não consegue mostrar com clareza. A validação na escrita recusa revisão dentro de qualquer contêiner (422), para não prometer uma aprovação que não acontece.

**O que está pendente fica no `agent_run`.** O run pausado do workflow ganha `pending_steps` com um resumo por requisito ativo:

- nome da etapa e `when`;
- mensagem;
- prazo;
- até 4.000 caracteres da saída, quando `when` é `after`.

É o que a página Aprovações lista. Os requisitos completos continuam só no run do Agno.

**A decisão segue a rota do AgentOS.** O painel lê o run pelo `GET` do AgentOS e marca o requisito ativo (`confirmed`, e `rejection_feedback` na recusa). Depois devolve a lista no `continue`, pelo BFF. Nenhuma rota própria decide aprovação, como na confirmação de tool.

**O `TrackedWorkflow` acompanha o `continue`.** Ele atualiza o mesmo `agent_run`: `paused` de novo com os novos pendentes, ou o desfecho final. As etapas que rodam depois do `continue` ficam com o mesmo `parent_run_id`.

**No modo teste, a pausa aparece no próprio painel**, com aprovar e recusar. Na suíte, um caso que chega numa revisão termina em erro "pausado". O caso testa o caminho até a revisão, e aprovar sozinho esconderia exatamente o que a revisão protege.

## Alternativas descartadas

- **Rota própria de aprovação que chama o workflow.** Repetiria o controle de acesso e o gate de aprovação do AgentOS, e duas rotas para continuar o mesmo run dariam corrida entre elas.
- **Guardar os requisitos completos no `agent_run`.** O `StepRequirement` carrega o `step_input` com a sessão do workflow, que pode ser grande e repetiria dado que já está no banco do Agno.
- **Revisão dentro de condição, ramo paralelo e laço.** Na condição, o Agno 3.1.8 ignora a revisão da etapa interna. O Agno aceita revisão por volta de laço (`requires_iteration_review`). Ela fica para quando houver um uso claro. Pausar um ramo e seguir os outros é um modelo de execução diferente.
- **Editar a saída na aprovação (`edited_output`).** É útil, mas pede editor e diff na página Aprovações. Fica para depois. Por enquanto a recusa com motivo e `retry` cobre a correção.

## Consequências

- Workflows com aprovação humana no meio deixam de precisar ser quebrados em dois.
- A página Aprovações passa a ter dois tipos de pendência: tool de agente e etapa de workflow.
- O run do workflow pausado conta como `paused` no analytics, como o do agente com tool pendente, e não entra na taxa de erro.
- Uma revisão sem prazo pode ficar parada indefinidamente. O painel mostra há quanto tempo cada pendência espera.
- Migration nova: `agent_run.pending_steps`.

## O que me faria reverter

- O AgentOS mudar o contrato do `continue` de workflow, por exemplo passando a mesclar requisitos por `step_id` em vez de substituir a lista. Nesse caso, o painel manda só o requisito decidido.
- O Agno passar a pausar etapa dentro de condição. Nesse caso, a revisão passa a valer também ali.
- Pedido recorrente de revisão em ramo paralelo. Nesse caso, a pausa passa a valer por ramo, com o contêiner esperando todos.
