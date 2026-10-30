# ADR-0028 — Revisão humana completa: editar a saída, revisar cada volta de laço e registrar as decisões

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-10-30

## Contexto

O ADR-0023 trouxe a revisão humana numa etapa do workflow: confirmar antes de rodar ou aprovar a saída depois. Ele deixou três coisas de fora:

- **Editar a saída na aprovação.** Hoje o revisor só aprova ou recusa. Para corrigir um valor ou uma vírgula, ele recusa com motivo e a etapa roda de novo, pagando outra chamada de modelo, sem garantia de que o ajuste venha certo.
- **Revisão por volta de laço.** Num laço de rascunho e revisão, quem decide se a volta ficou boa é a regra de parada ou o limite de voltas. Uma pessoa não consegue dizer "está bom, pode seguir" ou "mais uma volta, e corrija isto".
- **Registro de quem decidiu.** O run do workflow guarda as etapas pendentes (`pending_steps`), mas não guarda quem aprovou ou recusou, quando, com que motivo e, numa edição, o que mudou. Para um fluxo de reembolso ou contrato, essa é a parte que a auditoria pede.

Verificado no Agno 3.1.8 instalado:

- `StepRequirement.edited_output` (`workflow/types.py:890`) é lido no continue (`from_dict`, `:1228`). Ele confirma a etapa e troca a saída dela pela editada antes da próxima (`workflow/workflow.py:7005`).
- `HumanReview(requires_iteration_review=True)` no `Loop` (`workflow/loop.py:544`) pausa ao fim de cada volta, menos a última.
  - Aprovar encerra o laço, mantém a saída da volta e segue o workflow.
  - Recusar com `on_reject="retry"` roda mais uma volta e leva o motivo junto (`workflow/workflow.py:6921-6940`).
  - O reinício supõe uma etapa por volta: o próprio código avisa que laço com várias etapas por volta precisaria agrupar os resultados (`:6936`).
- O continue do AgentOS recebe a lista de `step_requirements`, mas não o usuário. O `sub` do token já é lido no `RevocationMiddleware` (`app/integrations.py`), antes de a requisição chegar ao AgentOS.

## Decisão

**Saída editada na aprovação.** O painel manda o requisito ativo com `edited_output` pelo mesmo `continue` do AgentOS. Nenhuma rota própria decide aprovação, como no ADR-0023. A edição vale para etapa com revisão depois da saída e é texto, com até 20 mil caracteres. Se o agente da etapa tem saída estruturada (ADR-0027), o JSON editado segue como texto: quem edita é responsável por mantê-lo no formato, e a suíte do workflow pega a regressão.

**Revisão por volta de laço.** O nó `loop` do payload ganha `review`, com mensagem e prazo opcionais. Ele vira `HumanReview(requires_iteration_review=True, on_reject="retry")`. A validação na escrita exige:

- o laço no nível principal, pela mesma regra do ADR-0023 para etapas dentro de contêiner;
- uma etapa por volta, pelo limite do Agno;
- nenhuma revisão na etapa de dentro, porque duas pausas por volta confundiriam quem aprova.

Aprovar a volta encerra o laço. Pedir outra volta exige comentário, que vira o retorno para a próxima volta.

**Registro das decisões no run.** O `agent_run` do workflow ganha `review_log`, uma lista com uma entrada por decisão. Cada entrada leva:

- a etapa e o tipo da decisão: aprovada, recusada, editada, volta aprovada ou nova volta pedida;
- quem decidiu, pelo `sub` do token;
- quando;
- o motivo, se houve;
- na edição, o texto antes e depois, com os dados pessoais mascarados como na memória (ADR-0025).

O `RevocationMiddleware` passa a guardar o `sub` num `ContextVar`, e o `TrackedWorkflow.acontinue_run` lê dali. O token é conferido pelo Agno logo depois, então um token inválido não chega ao continue. A página Aprovações e a árvore de execução mostram o histórico.

## Alternativas descartadas

- **Rota própria de aprovação com o usuário no corpo.** Duplicaria o `continue` do AgentOS e teria que reconstruir a retomada do workflow, que é a parte frágil. O usuário vem do token, e não do corpo, para não ser forjado.
- **Registrar em tabela de auditoria separada.** A decisão é parte do run, e o histórico é lido junto com ele. Uma coluna JSON no próprio `agent_run` evita mais uma consulta por run e uma retenção separada.
- **Revisão por volta em laço com várias etapas.** O Agno não agrupa os resultados da volta para retomar. Aceitar daria um laço que retoma com resultados trocados.
- **Diff estruturado no servidor.** O diff é para quem lê e sai no painel a partir do antes e depois gravados. O servidor guarda só os dois textos.

## Consequências

- Corrigir uma saída deixa de custar outra chamada de modelo. O texto editado segue para a próxima etapa como se fosse a saída do agente, e o registro mostra que houve edição.
- Em laço de rascunho, a pessoa decide quando a volta está boa, e o limite de voltas vira só um teto.
- A auditoria passa a responder quem decidiu cada pausa e o que mudou. O texto antes e depois fica mascarado, mas continua sendo conteúdo da conversa: a página Aprovações já é restrita ao dono do run e ao owner (Fase 28), e o registro segue essa regra.
- Uma migration: `agent_run.review_log`.

## O que me faria reverter

Se o Agno passar a agrupar as etapas da volta na retomada, a revisão por volta pode aceitar laço com várias etapas. Se a auditoria precisar de retenção diferente da do run, o registro migra para tabela própria.
