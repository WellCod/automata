# ADR-0013 — Guardrails por agente, versionados no payload, com regras brasileiras próprias sobre os hooks do Agno

**Status:** Aceito em 2026-10-19, com a Fase 14 entregue (#95–#103) (proposto em 2026-10-16)
**Data:** 2026-10-16

## Contexto

Hoje nada fica entre a mensagem do usuário e o modelo. Um cliente que cola CPF ou número de cartão no chat manda o dado ao provider e ele fica gravado na sessão. Um texto pedindo para o agente ignorar as instruções chega ao modelo como qualquer outro. Com o RAG (ADR-0012), documentos também viram vetor de injeção. Não há como dizer "este agente não fala de política" nem limitar o tamanho da entrada.

Verificado no Agno 2.8.7 instalado:

- `Agent` e `Team` aceitam `pre_hooks` e `post_hooks`: lista de funções ou de `BaseGuardrail` (`check`/`async_check(run_input)`). Os pre-hooks rodam depois de ler a sessão e antes de montar as mensagens e chamar o modelo. Bloquear ali não custa token.
- Só `InputCheckError` e `OutputCheckError` (`agno/exceptions.py`, com `check_trigger`, `error_id` e `additional_data`) interrompem o run. Qualquer outra exceção de hook é só logada.
- Ao bloquear, o run não-stream volta com `status=ERROR` e `content` igual à mensagem da exceção, sem levantar. O stream emite `RunError` com `error_type="input_check_error"`, `error_id` (`pii_detected`, `prompt_injection`…) e `additional_data`, e encerra. Nos dois casos o run é persistido na sessão **com o input original**.
- Os guardrails prontos não servem como estão:
  - `PIIDetectionGuardrail` só tem padrões dos EUA (SSN, telefone de 10 dígitos), não tem CPF nem CNPJ e não valida dígito verificador. Mascarar troca o trecho por asteriscos no input antes do modelo.
  - `PromptInjectionGuardrail` compara substrings com uma lista fixa em inglês. Uma lista passada substitui a padrão em vez de somar, e há termos com falso positivo comum ("system prompt", "act as if").
  - `OpenAIModerationGuardrail` chama a API de moderação da OpenAI.
- Os guardrails prontos só funcionam como pre-hook. Em `post_hooks` o `check()` é chamado sem `run_input`, falha e é ignorado em silêncio. Validar a saída exige função própria que receba `run_output` e levante `OutputCheckError`.
- O tracing não tem span para hook: o bloqueio aparece só como erro no span do run.
- No projeto, `tracking.py` já grava o bloqueio como `error` com a mensagem, mas não guarda o motivo (`error_id`). O bloqueio entra na taxa de falha do analytics como se fosse defeito.

## Decisão

Guardrails são configuração do agente e entram no payload versionado (`guardrails` no `ConfigPayload`): mudar uma regra é rascunho, publicação e rollback, como as instruções. A factory transforma a seção em `pre_hooks` (entrada) e `post_hooks` (saída) do `Agent`, do líder do time e de cada membro, que leva os guardrails da própria versão.

As regras são implementações próprias de `BaseGuardrail`, não as do Agno:

| Regra | Entrada / saída | Comportamento |
|---|---|---|
| Dados pessoais | entrada | CPF e CNPJ (com dígito verificador), cartão (com Luhn), e-mail e telefone brasileiro. Modo `bloquear` ou `mascarar`, por tipo |
| Injeção de prompt | entrada | Lista própria em português e inglês, sem acento e sem maiúscula, mais termos extras do agente (que somam à lista, não substituem) |
| Tópicos proibidos | entrada | Termos ou expressões definidos pelo agente |
| Tamanho máximo | entrada | Limite de caracteres da mensagem |
| Moderação | entrada | Opcional, pela API de moderação da OpenAI; exige `OPENAI_API_KEY` |
| Saída | saída | Dados pessoais e termos proibidos na resposta |

O run bloqueado ganha status próprio, `blocked`, e o motivo (`blocked_by`: `pii_detected`, `prompt_injection`, `off_topic`, `input_too_long`, `moderation`, `output_not_allowed`) em `agent_run`. Quem conversa recebe uma mensagem configurável por agente ("Não posso ajudar com isso por aqui…"), não a mensagem técnica.

## Alternativas descartadas

**Usar os guardrails do Agno como estão.** CPF, CNPJ e telefone brasileiro não são detectados, e o telefone dos EUA casa com trechos numéricos comuns aqui. Sem dígito verificador, qualquer sequência de 11 dígitos (número de pedido, protocolo) vira bloqueio. A lista de injeção só em inglês deixa passar "ignore as instruções anteriores".

**Guardrail global da instância, igual para todos os agentes.** Um agente de RH precisa receber CPF; um de atendimento público não. Um padrão por instância pode vir depois, como ponto de partida ao criar agente, sem tirar a decisão do agente.

**Guardrail fora do payload versionado, como bases e servidores MCP.** Base e servidor mudam por motivo operacional (documento novo, token rotacionado). Guardrail muda o comportamento do agente: precisa aparecer no diff de versões e voltar com rollback. Afrouxar uma regra sem rastro é exatamente o que uma auditoria vai perguntar.

**Classificador por LLM em toda mensagem** (tópico, injeção, toxicidade). Pega o que lista de termos não pega, mas soma latência e custo a cada mensagem e precisa de um modelo que também pode ser enganado. Fica como regra opcional futura, por agente, quando houver caso que justifique.

**Contar o bloqueio como `error`.** O analytics passaria a mostrar o guardrail funcionando como taxa de falha do agente, e o alerta de falha dispararia por tentativa de injeção.

## Consequências

- `ConfigPayload` ganha `guardrails` com padrão desligado. Agentes existentes não mudam até alguém publicar uma versão com regras. `schema_version` continua 2 (campo novo com padrão).
- Bloquear não custa token de modelo, exceto a moderação, que é uma chamada à OpenAI por mensagem com latência própria e manda o texto para fora. Fica desligada por padrão e o painel avisa disso.
- **O dado bloqueado não pode ficar gravado.** O Agno persiste o run bloqueado com o input original. A regra de dados pessoais mascara o input antes de levantar o bloqueio, então a sessão guarda a versão mascarada. `blocked_by` e o detalhe guardam o tipo detectado, nunca o valor.
- **Guardrail de saída em stream chega tarde.** O texto já foi entregue enquanto era gerado quando o post-hook roda. No stream (modo teste, chat) o run fica marcado como bloqueado e o painel avisa, mas o usuário já viu a resposta. No não-stream (integrações REST e MCP) a resposta é trocada pela mensagem de bloqueio antes de sair. A documentação precisa dizer isso com todas as letras.
- Status `blocked` em `agent_run`: o analytics conta bloqueios por motivo e tira os bloqueios da taxa de falha. Migration nova; runs antigos ficam como estão.
- `tracking.py` passa a ler o `error_id` do `RunError` e da exceção para preencher `blocked_by`. O fallback que hoje perde a mensagem no stream precisa guardar o conteúdo do evento.
- Falso positivo tem custo: o agente deixa de responder a quem tinha motivo legítimo. As listas de injeção ficam pequenas e conservadoras, cada regra é ligada por agente, e o modo teste mostra qual regra bloqueou para o editor ajustar.
- Times: o líder aplica os próprios guardrails à mensagem do usuário; cada membro aplica os seus à tarefa que recebe do líder.

## O que me faria reverter

- Taxa de bloqueio por falso positivo medida acima de 2% das mensagens de algum agente: rever as listas ou passar a regra a classificador.
- Injeção que passa pela lista aparecer em produção com dano real: adicionar classificador por LLM como regra opcional.
- Exigência regulatória de política única para toda a instância (LGPD num cliente específico): padrão de instância obrigatório, que o agente pode endurecer mas não afrouxar.
