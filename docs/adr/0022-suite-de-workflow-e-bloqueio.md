# ADR-0022 — Suíte de testes para workflows e caso que espera bloqueio de guardrail

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-10-21

## Contexto

A suíte de testes (ADR-0015) roda em agentes e times. Duas lacunas ficaram de fora.

**Workflow não tem suíte.** A rota recusa com 422 ("Workflow ainda não tem suíte de testes"). Um workflow publica, agenda e roda sem nenhuma checagem automática, e ele é justamente o lugar onde a regra de uma condição ou o fim de um laço pode mudar o caminho inteiro sem ninguém notar.

**Guardrail não tem caso que espera bloqueio.** Os evals de guardrail (Fase 14) rodam no CI do Automata, contra regras fixas. A configuração de cada agente (tópicos proibidos, termos extras de injeção, PII em modo bloquear) não tem teste. Quem edita os tópicos de um agente não sabe se a mensagem que devia ser barrada continua barrada.

Verificado no Agno 3.1.8 instalado (`agno.eval.suite`):

- `Case` aceita `agent` ou `team`, e o `__post_init__` só confere que exatamente um está preenchido. Quem roda o caso chama `runner.arun(input, stream=True, yield_run_output=True, ...)` e espera um `RunOutput` ou `TeamRunOutput` no stream.
- **Só run `completed` é avaliado.** Run com status de erro vira erro do caso, sem juiz, sem tools e sem scorer.
- Guardrail que barra levanta `InputCheckError` ou `OutputCheckError`. O Agno marca o run com `RunStatus.error` e põe a mensagem de bloqueio no conteúdo. Para a suíte, um bloqueio é indistinguível de uma falha do modelo.
- `WorkflowRunOutput` traz `content` (a saída final) e `step_results` (um `StepOutput` por etapa que rodou, com `step_name` e as etapas internas de paralelo, condição e laço).

No código atual:

- O `BlockLog` de cada agente ou time guarda a regra que barrou (ADR-0013), e o tracking grava `blocked_by` no run a partir dele.
- O factory do workflow (`load_workflow`, `build_nodes`) monta o workflow do zero a cada request, a partir da versão.

## Decisão

**Checagem `blocked`, para agente e time.** O caso passa quando o run é barrado por guardrail de entrada ou de saída. Com `rule` preenchido, só passa se a regra que barrou for essa: dados pessoais, injeção, tópico, tamanho, moderação ou saída barrada.

- A checagem lê o `BlockLog` do agente ou time do caso, não o status do run. Bloqueio por orçamento não conta, porque não é comportamento do agente.
- **É a única checagem do caso.** Um run barrado não tem resposta para comparar, chamar tools ou julgar. A validação na escrita recusa `blocked` junto de outra checagem (422).
- Run que respondeu sem bloquear reprova o caso com "respondeu sem bloquear".

**Suíte para workflow, pelo mesmo runner.** O workflow entra no `Case` como `agent=` através de um adaptador: um objeto com `id` e `arun` que roda o workflow montado pela factory (`stream=False`) e devolve um `RunOutput` com o conteúdo final, o status traduzido e as etapas que rodaram em `metadata`. O resto vem do runner do Agno sem mudança: timeout por caso, juiz, scorer e o resultado gravado caso a caso.

- **Checagens do workflow:** texto e juiz, sobre a saída final, e a nova `steps`: lista de etapas que precisam ter rodado, com opção de exigir também que nenhuma outra rode. É ela que pega a condição que mudou de caminho.
- `tools` e `blocked` ficam fora (422): as tools e os bloqueios são de cada etapa, que já tem a própria suíte.
- **Turnos anteriores (`context`) ficam fora em workflow.** Workflow roda uma entrada por vez, sem conversa.
- Gate de publicação, agendamento, comparação entre execuções, aviso de regressão e token de integração passam a valer para workflow sem mudança: todos leem o `eval_run`, que não sabe o tipo do config.

## Alternativas descartadas

- **Runner próprio para workflow, fora do `agno.eval.suite`.** Repetiria o timeout, o juiz e o formato do resultado, e as duas suítes divergiriam na primeira atualização do Agno. O adaptador mantém um caminho só.
- **Checagem de bloqueio pelo texto da mensagem de bloqueio.** Passaria com o modelo respondendo a mesma frase e não diferencia a regra. O `BlockLog` é o que o tracking já usa.
- **Bloqueio junto de outras checagens.** Não há o que checar num run barrado. Aceitar a combinação criaria caso que nunca passa.
- **`tools` por etapa no workflow.** Cada etapa é um agente ou time com suíte própria. No workflow, o que importa é o caminho e a saída final.

## Consequências

- A configuração de guardrail de cada agente ganha teste que roda no gate e no agendamento. Mudar um tópico proibido sem querer aparece como regressão.
- Workflows passam a ter gate de publicação e aviso de regressão como agentes e times.
- O adaptador depende de o `Case` aceitar um objeto com `arun` em `agent=`. Uma atualização do Agno que passe a exigir `Agent` de verdade quebra a suíte de workflow, e os testes de integração pegam isso no CI.
- O caso de workflow custa a soma das etapas. O consumo já entra no `eval_run` pelo `eval_run_id` de cada etapa.

## O que me faria reverter

- O Agno passar a aceitar `workflow=` no `Case`. Nesse caso, o adaptador sai e o workflow entra direto.
- Pedido de checar a saída de uma etapa do meio, e não só a final. Nesse caso, a checagem `steps` ganha regra de texto por etapa.
