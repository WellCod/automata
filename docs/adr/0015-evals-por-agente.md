# ADR-0015 — Evals por agente no painel, com casos fora da versão e o runner de suíte do Agno

**Status:** Aceito
**Data:** 2026-10-20

## Contexto

Publicar uma versão hoje depende de alguém abrir o modo teste, mandar duas ou três mensagens e achar que está bom. A versão é imutável e o rollback é imediato (ADR-0002), mas nada diz, antes de publicar, que a mudança no prompt não quebrou o que funcionava. Em software isso se resolve com teste de regressão. Em agente, o equivalente é uma suíte de casos: entrada, e o que precisa ser verdade sobre a resposta.

O repositório já tem evals, mas só no CI e sobre código nosso: regras de guardrail, regras de workflow e recuperação do RAG. Quem edita agente no painel não escreve pytest, e o comportamento que muda a cada publicação é o do prompt, não o do código.

Verificado no Agno 2.8.7 instalado:

- **`agno.eval.suite`**: runner de suíte com `Case`, `arun_cases`, `CaseResult` e `SuiteResult`. Cada `Case` tem uma entrada, um agente **ou** um time, timeout próprio e três tipos de checagem, combináveis:
  - **juiz** por LLM (`criteria`, via `AgentAsJudgeEval`), binário ou nota de 1 a 10 com limiar;
  - **tools esperadas** (`expected_tool_calls`, via `ReliabilityEval`), com ou sem tolerância a tools extras;
  - **`Scorer`**, qualquer objeto com `async ascore(run, expected) -> Score`, avaliado em processo.
- O runner executa em sequência, emite eventos por caso (`on_case_start`, `on_case_end`, `on_run_event`) e não escreve no console. Um caso sem nenhuma checagem é recusado na construção: suíte vazia não passa em silêncio.
- **Limites:**
  - não aceita workflow;
  - um run que termina em erro, inclusive bloqueio de guardrail, conta como caso falho e não chega aos checadores;
  - sem `judge_model`, o `AgentAsJudgeEval` cai num modelo da OpenAI por padrão, e o juiz exige saída estruturada;
  - o consumo do juiz não aparece no `CaseResult`.
- O AgentOS expõe `POST /eval-runs`: uma entrada por chamada, resultado na tabela de evals do Agno, sem agrupamento em suíte e sem vínculo com versão de configuração.

Cada salvamento de rascunho cria uma `agent_config_version` nova (`update_draft`). Um id de versão identifica, portanto, um conteúdo exato.

## Decisão

**Casos de teste por config, fora do payload versionado.** Tabela própria (`eval_case`) ligada ao `agent_config`, com nome, entrada e checagens. Os casos não entram na versão. Se entrassem, um rascunho poderia afrouxar os próprios testes e passar. O histórico de edição fica em `updated_by` e `updated_at`, e cada execução guarda uma cópia dos casos como estavam, para o resultado continuar legível depois que o caso mudar.

**Checagens de um caso**, ao menos uma, até cinco:

| Tipo | Como roda | Custo |
|---|---|---|
| Texto da resposta | `Scorer` próprio que reaproveita as regras dos workflows (contém, não contém, começa com, vazia), sem diferenciar maiúsculas | nenhum |
| Tools chamadas | `expected_tool_calls` do Agno; nomes vêm do agente: `buscar_<slug>` das bases e tools MCP com prefixo | nenhum |
| Critério do juiz | `criteria` do Agno, binário ou nota com limiar, com modelo escolhido na suíte | tokens do juiz |

**Execução com o runner do Agno, em background.** Rodar a suíte cria um `eval_run` (fila → rodando → concluído ou falha), com o alvo indicado por `version_id`: rascunho, versão vigente ou qualquer versão publicada. A API monta o agente ou time daquela versão com a mesma factory dos runs reais (`agent_from`, `team_from`), constrói os `Case`s e chama `arun_cases`. O `on_case_end` grava cada `eval_result` assim que o caso termina, e o painel acompanha por polling. Uma execução por config por vez; timeout de 120 s por caso; até 50 casos por config.

**Juiz com modelo nosso e medido.** O modelo do juiz é escolhido na suíte, entre os modelos da matriz com saída estruturada, e passado sempre como `judge_model`, para nunca cair no padrão do Agno. Ele é embrulhado num modelo medido, como o `MeteredEmbedder` do RAG (ADR-0012), que soma os tokens do juiz no consumo da execução.

**Runs de eval separados das conversas.** As execuções dos casos passam pelo mesmo `RunTracking`. Uma `ContextVar` com o id do `eval_run`, no mesmo padrão do `parent_run_id` dos workflows, marca `agent_run.eval_run_id` e `usage_event.eval_run_id`. O analytics de conversas, latência e falhas ignora esses runs. O custo continua no metering, porque é gasto real, mas aparece separado, como "custo de testes".

**Gate de publicação opcional, por config.** Uma flag `require_passing_evals` no `agent_config`, fora da versão, pelo mesmo motivo dos casos. Com ela ligada, publicar exige uma execução concluída sobre o `draft_version_id` atual em que todos os casos passaram. Como cada rascunho salvo é uma versão nova, editar o rascunho invalida o resultado anterior sem hash nem comparação de payload.

**Comparação entre versões.** Rodar a mesma suíte no rascunho e na vigente mostra, caso a caso, o que passou a falhar (regressão) e o que passou a passar.

**Escopo da primeira versão:** agente e time. Workflow fica de fora, porque o runner não o aceita.

## Alternativas descartadas

- **Usar o `POST /eval-runs` do AgentOS como está.** Uma entrada por chamada, resultado sem vínculo com a versão e sem conceito de suíte. Além disso, a rota troca o modelo do agente resolvido para avaliar, e as rotas do AgentOS não são modificadas (regra do projeto). Montar a suíte por cima dela seria reimplementar o runner que o próprio Agno já tem.
- **Casos dentro do payload versionado.** Daria histórico de graça, mas o rascunho que muda o prompt também poderia mudar o teste. Teste que acompanha a mudança não pega regressão.
- **Escrever um runner próprio.** O `agno.eval.suite` já cobre timeout por caso, juiz, tools esperadas, scorer, abortar em cancelamento e evidência por caso. Reescrever isso não traz nada que justifique manter código paralelo à versão do Agno.
- **Juiz no modo demo como aprovado.** No `DEMO_REPLAY` o modelo devolve texto gravado e o juiz não consegue responder no formato estruturado. Fingir aprovação ensinaria a confiar num resultado que ninguém avaliou. No modo demo, checagem de juiz aparece como "não avaliada", e as de texto e de tools rodam normalmente.
- **Gate sempre ligado.** Agente sem casos não poderia ser publicado, e o primeiro uso da plataforma viraria escrever teste antes de ver o agente funcionar. Opt-in por config, desligado por padrão.

## Consequências

- Publicar ganha uma evidência objetiva, por versão, com o mesmo agente que vai para produção: mesma factory, mesmas tools, bases e guardrails.
- O gate valida a configuração, não as dependências. Uma base de conhecimento reindexada, um servidor MCP que mudou ou um membro de time que segue a versão vigente podem mudar o comportamento depois do teste. A comparação entre versões e rodar a suíte de novo cobrem parte disso; agendamento fica para depois.
- Caso que esperava bloqueio de guardrail não cabe no runner, porque bloqueio vira erro. Esse comportamento continua coberto pela eval de guardrails do CI (ADR-0013).
- Juiz por LLM é não determinístico: o mesmo caso pode oscilar perto do limiar. A interface mostra o motivo do juiz e a nota, e o painel recomenda usar texto e tools quando a regra for objetiva.
- Rodar a suíte tem custo de tokens: dos casos e do juiz. O custo aparece na execução e no metering, separado das conversas.
- Duas migrations: tabelas de caso, execução e resultado; colunas `eval_run_id` em `agent_run` e `usage_event` e a flag no `agent_config`.

## O que me faria reverter

- O runner do Agno mudar de contrato a ponto de exigir adaptação a cada versão. Nesse caso, o runner próprio passa a valer o custo.
- A necessidade de versionar casos junto com o prompt, por exemplo times com fluxo de aprovação em que o teste também é revisado. Nesse caso, os casos entram numa versão própria, separada do payload.
