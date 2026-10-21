# ADR-0019 — Compactação de conversa por agente, versionada no payload, com limite baixo e resumo pelo modelo do agente

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-10-21

## Contexto

Até a Fase 17, as conversas não tinham memória: o factory nunca ligava `add_history_to_context`, e cada mensagem chegava sozinha ao modelo. O #134 corrigiu isso, e agora agentes e líderes de time levam os últimos 5 turnos da sessão (`HISTORY_RUNS`).

A correção resolve a memória curta, mas cria dois problemas:

- **Conversa longa perde o começo.** No sexto turno, o primeiro sai da janela. Num atendimento em que o número do pedido foi dito no início, o agente esquece.
- **Cada turno custa os cinco anteriores inteiros.** Turnos com respostas longas ou com resultado de tool grande deixam cada mensagem nova mais cara, sem limite de tamanho, só de quantidade.

Verificado no Agno 3.1.8 instalado (3.1.2 trouxe a compactação):

- `Agent(compaction=Compaction(...))`: quando o contexto passa de `compact_at_tokens`, os turnos antigos são guardados como estavam e trocados, só na mensagem ao modelo, por um resumo gerado. O registro da sessão não muda.
- **Com `compact_at_tokens`, a compactação controla a janela.** Ela manda tudo desde o último resumo até o limite, e `num_history_runs` deixa de valer.
- `uncompacted_runs` (padrão 5) é quantos turnos recentes ficam inteiros. `instructions` orienta o resumo (por exemplo, "mantenha números de pedido"). O padrão de `compact_at_tokens` é **150 mil tokens**.
- O resumo usa o modelo do agente, salvo outro em `model`. O consumo do resumidor entra nos totais do run (`accumulate_model_metrics`, tipo `compaction_model`), e a medição de consumo que já temos registra esse custo sem mudança.
- Com `search_compacted_messages`, o agente ganha uma tool de busca no histórico compactado, para recuperar um detalhe que o resumo deixou de fora.
- A contagem de tokens é local: tiktoken, se instalado, ou uma estimativa por caracteres. O tiktoken não está na imagem, então vale a estimativa, sem chamada de rede.
- **`Team` não aceita `compaction` na 3.1.8.**
- Os registros de compactação ficam numa tabela do Agno (`agno_compactions`), criada sob demanda no mesmo banco das sessões.

## Decisão

**Compactação opcional por agente, versionada no payload.** O payload ganha uma seção `conversation`:

- `compaction`, desligado por padrão;
- `compact_at_tokens`, de 4.000 a 128.000, padrão **16.000**;
- `keep_recent_runs`, de 1 a 20, padrão 3;
- `summary_instructions`, até 500 caracteres;
- `search_history`, padrão ligado.

O comportamento da conversa é parte do agente: entra na versão como instruções e guardrails, passa pelo rascunho e pela publicação, e a suíte de testes pega o efeito antes de publicar.

**Limite padrão bem abaixo do Agno.** Os 150 mil tokens do Agno quase nunca disparam numa conversa de atendimento e deixariam cada turno mandar o histórico inteiro até lá, mais caro que os 5 turnos de hoje. Com 16 mil, a janela fica parecida com a atual em custo e ganha o resumo do que ficou para trás. O painel mostra o limite em tokens com uma referência em páginas de texto.

**O resumo usa o modelo do próprio agente.** Isso dispensa outra escolha de modelo e outra chave, e o custo sai no consumo do agente. Um modelo próprio para o resumo fica para depois, se o custo pedir.

**Só agente nesta fase.** Time recusa a seção na validação de escrita (422), porque o `Team` do Agno não aceita compactação. Os membros de um time são agentes, mas rodam dentro da delegação do líder e não guardam sessão própria. O líder segue com a janela de 5 turnos.

**Sem compactação, nada muda.** O agente continua com `HISTORY_RUNS`.

## Alternativas descartadas

- **Ligar a compactação para todos os agentes.** Mudaria o comportamento e o custo de agentes publicados sem nova versão. Isso contradiz o modelo de versões (ADR-0002), em que toda mudança de comportamento passa por rascunho e publicação.
- **Aumentar `HISTORY_RUNS`.** Mais turnos inteiros resolvem o esquecimento só até o próximo limite e encarecem todo turno. O resumo guarda o essencial por uma fração do tamanho.
- **Memória de usuário do Agno (`update_memory_on_run`, aprendizados).** Ela guarda fatos entre sessões, o que é outro problema, com outro cuidado de privacidade: fatos sobre o cliente persistidos além da conversa. Pode virar uma fase própria, com decisão sobre retenção e PII.
- **Usar o limite padrão de 150 mil.** Ver acima: o resumo quase nunca entraria, e o custo por turno cresceria.

## Consequências

- Conversas longas guardam o essencial do começo, e o custo por turno fica limitado pelo limite escolhido, não pelo tamanho das respostas.
- O resumo é uma chamada de modelo a mais quando a conversa cruza o limite, cobrada no agente. O analytics mostra no consumo do agente.
- O resumo pode perder um detalhe. A tool de busca no histórico compactado recupera o que ficou de fora, e as `summary_instructions` dizem o que não pode sumir.
- Com a compactação ligada, a janela deixa de ser "5 turnos" e passa a ser "até o limite". A suíte de testes com turnos anteriores (ADR-0016) mede o efeito.
- O payload ganha uma seção opcional com padrão desligado. Versões antigas continuam válidas sem conversão.

## O que me faria reverter

- Resumos que perdem informação com frequência nas suítes dos clientes, mesmo com instruções. Nesse caso, a opção sai do painel, e a janela de turnos volta a ser a única.
- O `Team` do Agno passar a aceitar compactação. Nesse caso, a seção vale também para o líder do time.
