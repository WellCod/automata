# ADR-0038 — Roteador, entrada por etapa, histórico no workflow e casos de suíte a partir das conversas

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-04

## Contexto

O workflow (ADR-0014) e a suíte (ADR-0016 e ADR-0022) deixaram pendências:

- **Só dá para ramificar em dois caminhos.** Uma triagem com cinco destinos (troca, reembolso, entrega, cobrança e o resto) vira cinco condições aninhadas, e o editor fica ilegível. O ADR-0014 deixou o roteador e a entrada por etapa para depois.
- **A etapa sempre recebe a saída da anterior.** Uma etapa de revisão que precisa da pergunta original do cliente recebe só o rascunho.
- **O workflow não lembra a conversa.** Cada mensagem roda o fluxo do zero. O caso de suíte de workflow não aceita turnos anteriores (ADR-0022), porque sem histórico eles não teriam efeito.
- **A checagem de texto olha só a saída final.** Para conferir que a triagem classificou certo, é preciso que a etapa final repita a classificação.
- **Os casos nascem um a um.** O ADR-0016 deixou para depois a geração em lote a partir das conversas.

Verificado no Agno 3.1.8 instalado:

- **`Router(name, choices, selector)`** (`workflow/router.py`): o `selector` recebe o `StepInput` e pode devolver o nome de uma das `choices`. Lista vazia não roda nada.
- **`Step._prepare_message(message, previous_step_outputs)`** monta a entrada do agente da etapa. Ela é a saída mais funda da última etapa, ou a mensagem original quando não há etapa anterior. Uma subclasse de `Step` pode trocar essa montagem, e as duas execuções do Agno (síncrona e assíncrona) passam por ela.
- **`Workflow(add_workflow_history_to_steps, num_history_runs)`** leva às etapas os últimos runs do workflow na mesma sessão.
- O runner da suíte roda os turnos anteriores no `setup` do `Case` com `runner.arun(...)`. O adaptador de workflow (`WorkflowUnderTest`) é um gerador, então o setup precisa chamar o workflow direto.

## Decisão

**Roteador.** Um nó `router` no workflow tem:

- `routes`: de 2 a 5 caminhos, cada um com uma `rule` (as mesmas regras do ADR-0014, sobre a mensagem ou a saída anterior) e uma etapa;
- `default`: uma etapa opcional.

O primeiro caminho cuja regra casa roda. Sem nenhum, roda o padrão ou nada. Ele vira um `Router` do Agno, com um `selector` nosso que devolve o nome da etapa. Uma etapa dentro do roteador não tem revisão humana, pela mesma regra dos contêineres (ADR-0023).

**Entrada por etapa.** A etapa ganha `input`:

- `previous`: a saída da etapa anterior, como hoje e por padrão;
- `original`: a mensagem do usuário;
- `template`: um texto de até 2000 caracteres. Nele, `{entrada}` vira a mensagem do usuário, `{anterior}` a saída da etapa anterior e `{etapa:Nome}` a saída de uma etapa que já rodou. Um nome que não existe no workflow dá erro na escrita.

Ela vira uma subclasse de `Step` que troca o `_prepare_message`.

**Histórico no workflow.** `workflow.history_runs`, de 0 (padrão) a 5, liga `add_workflow_history_to_steps` com esse número de runs. Com o histórico ligado, o caso de suíte do workflow aceita turnos anteriores, rodados no workflow na mesma sessão antes do turno avaliado. Sem histórico, a escrita recusa turnos anteriores, porque eles não teriam efeito.

**Checagem de texto numa etapa.** A checagem de texto do caso de workflow ganha `step`, opcional: com ele, a regra olha a saída daquela etapa. O adaptador da suíte guarda a saída de cada etapa que rodou. Uma etapa que não rodou falha a checagem.

**Casos em lote.** `GET /api/v1/configs/{id}/eval-cases/suggestions?limit=10` traz sugestões das conversas recentes do agente ou do time, nas mesmas regras da sugestão de um caso (ADR-0016):

- dados pessoais mascarados;
- sem run de teste, bloqueado ou de etapa;
- só as conversas de quem pede, a não ser para o owner.

A lista pula os runs que já viraram caso. Nada é gravado: o painel mostra as sugestões e salva as escolhidas.

## Alternativas descartadas

- **Roteador por CEL.** O CEL exige pacote extra e falha em silêncio com expressão errada, pelo mesmo motivo do ADR-0014.
- **Roteador pelo modelo** (o líder escolhe o caminho). Isso já existe: é o time no modo `route` (ADR-0011).
- **Gravar os casos em lote direto.** Caso ruim polui a suíte e trava o gate. A escolha fica com quem cuida do agente.

## Consequências

- Uma etapa com `template` não vê a saída anterior se o texto não a pedir. O editor mostra quais variáveis o texto usa.
- O histórico aumenta o contexto de toda etapa e o custo de cada run do workflow.
