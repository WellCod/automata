# ADR-0034 — Piso de guardrails da instância e classificador na saída

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-04

## Contexto

Os guardrails são por agente (ADR-0013) e começam todos desligados. Numa instância com dezenas de agentes, garantir que todos mascaram CPF depende de quem configura cada um lembrar de ligar. Um agente novo nasce sem proteção. O ADR-0013 deixou para depois um "padrão de guardrails da instância".

O classificador por modelo (ADR-0030) olha só a entrada. A resposta passa pelo guardrail de termos e de dados pessoais, mas não há como pegar uma resposta ofensiva, fora do assunto ou que revela as instruções internas do agente. O ADR-0030 deixou o classificador na saída para depois.

Verificado no Agno 3.1.8 instalado:

- `aexecute_post_hooks` (`agent/_hooks.py`) espera post hook assíncrono no `arun`. O `run()` síncrono pula hook assíncrono com um aviso no log. Todo run do Automata passa pelo `arun`: AgentOS, modo teste e suíte. Não há `run()` síncrono no código (`grep` em `app/`).
- O `Team` tem a mesma execução de post hooks (`team/_hooks.py`).
- O guardrail de saída atual (`app/guardrails/output.py`) troca a resposta antes de levantar `OutputCheckError`. No stream, o texto já foi entregue e o run só é marcado.

## Decisão

**Piso de guardrails da instância.** Uma tabela `instance_guardrails` (migration 0044, uma linha só) guarda um `GuardrailSettings` que vale como mínimo para todo agente e líder de time. Só o owner edita (scope `guardrails:admin`), em `GET` e `PUT /api/v1/instance-guardrails`. A escrita valida como a do agente: modelo do classificador na matriz, moderação só com chave.

A combinação é feita ao carregar a versão (`load_version`), então entrada, saída, exame de tool, memória e suíte recebem o efetivo. A regra é que o agente só endurece:

- dados pessoais: o modo mais forte (desligado < mascarar < bloquear), a união dos tipos e a união dos padrões próprios. Rótulo repetido fica com o da instância;
- injeção, moderação e exame de tool por termos ou classificador: ligado se qualquer um ligar;
- termos extras de injeção, tópicos proibidos e termos proibidos na saída: união;
- tamanho máximo da entrada: o menor;
- classificador, na entrada e na saída: com os dois definidos, o modelo e o escopo são os do agente, as checagens são a união, e a falha bloqueia se qualquer um pedir. Com um só, vale ele;
- mensagem de bloqueio: a do agente.

`GET /api/v1/configs/{id}/guardrails/effective` mostra o efetivo da versão vigente, ou do rascunho com `?draft=true`, e o painel marca o que veio da instância. O piso vale a partir do próximo run, sem publicar os agentes de novo, porque não é parte da versão. A mudança no piso fica no log com quem fez.

**Classificador na saída.** `guardrails.output.classifier` recebe:

- `model_id`;
- `checks`: `toxicity`, `off_topic` ou `prompt_leak`, que é a resposta revelar instruções internas, o prompt ou a configuração;
- `scope`, obrigatório com `off_topic`;
- `on_failure`: `allow` ou `block`.

Ele é um post hook assíncrono, depois do guardrail de termos e de dados pessoais. Ele reaproveita do classificador de entrada (ADR-0030) a marcação do texto como dado, a resposta em JSON estrito (fora do formato bloqueia sempre), o prazo de 10 s e o custo no agente pelo `record_side_usage`. O texto vai inteiro até 20 mil caracteres. Acima disso, vão o começo e o fim, como na entrada.

No não-stream, a resposta bloqueada é trocada pela mensagem de bloqueio antes de sair. No stream, o texto já saiu, então o run fica marcado como bloqueado, com o motivo, como o guardrail de saída de hoje.

## Alternativas descartadas

- **Piso copiado para cada agente ao salvar.** Mudar o piso exigiria salvar e publicar todos os agentes de novo, e um agente criado antes ficaria para trás.
- **O agente poder afrouxar o piso.** O piso existe porque quem configura o agente pode esquecer ou discordar. Afrouxar fica com o owner, no próprio piso.
- **Classificador na saída também no stream, antes de entregar.** Seria preciso segurar o texto até o fim da resposta, o que acaba com o stream. Quem precisa do bloqueio de fato usa o não-stream, como já vale para o guardrail de saída.

## Consequências

- Um piso com classificador ou moderação adiciona uma chamada por mensagem em todos os agentes. O painel mostra isso ao salvar o piso.
- O piso não é versionado: a versão de um agente publicada em outubro roda hoje com o piso de hoje. Para auditar o que valia num run, o registro de bloqueios do run guarda a regra que bloqueou.
- Workflow não tem guardrails próprios. Cada etapa é um agente e recebe o piso como qualquer agente.
