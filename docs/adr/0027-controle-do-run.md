# ADR-0027 — Controle do run: limite de tools, retry do provedor com modelo reserva e saída estruturada

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-10-30

## Contexto

O agente roda com o que o modelo decidir, e três situações ficam sem controle por agente:

- **Laço de tool.** Um modelo que erra a chamada de uma tool MCP tenta de novo e de novo. Cada volta é uma chamada de modelo paga. O orçamento mensal (ADR-0021) só barra o próximo run, não o laço do run atual, e o "limite de custo por run" ficou adiado.
- **Falha do provedor.** Um 429 ou 5xx da Anthropic ou da OpenAI vira run com erro. Ele conta na taxa de falha e pode disparar o alerta de pico de erro, mesmo que um segundo pedido segundos depois, ou outro modelo, resolvesse.
- **Resposta em texto livre.** Quem integra por token ou MCP para classificar, extrair ou rotear precisa de JSON e hoje faz parse de texto. A matriz de capabilities já tem `structured_output` e o formulário já mostra a caixa, mas ela não faz nada: o payload não tem schema (`app/agents/models_map.py`).

Verificado no Agno 3.1.8 instalado:

- `Agent.tool_call_limit` e `Team.tool_call_limit` (`agent/agent.py:198`, `team/team.py:282`). O limite chega ao modelo como `function_call_limit`: passado dele, as tools deixam de ser oferecidas e o modelo responde com o que tem.
- `Agent.retries` repete **o run inteiro**, tools incluídas (`agent/_run.py:426`). Já `Model.retries`, com `delay_between_retries` e `exponential_backoff` (`models/base.py:177-182`), repete só a chamada ao provedor que levantou `ModelProviderError`.
- `FallbackConfig` (`models/fallback.py`) com `on_error` e `on_rate_limit`. O `on_error` só cobre erro que vale repetir, como 5xx e rede. Erro 400, 401 ou 403 nunca é mascarado por um modelo reserva (`get_fallback_models`).
- `RunMetrics.details` traz o consumo por modelo, com `id` e tokens de cada um (`metrics.py`). Hoje o custo estimado usa só o modelo configurado.
- `output_schema` aceita `dict` com JSON Schema (`agent/agent.py:319`), e a resposta volta já como objeto.

## Decisão

**Uma seção `run` no payload, versionada como as outras.** Ela passa por rascunho, publicação e suíte. Todos os campos têm padrão vazio ou zero, então nenhum agente publicado muda sem uma nova versão.

**Limite de chamadas de tool por run** (`tool_call_limit`, de 1 a 100). Vale para o agente e para o líder do time. Não há limite próprio por membro: o membro herda o da própria versão quando roda sozinho.

**Retry do provedor, nunca do run.** `provider_retries`, de 0 a 3, vira `Model.retries` com backoff exponencial a partir de 1 s. O `Agent.retries` fica de fora porque repetiria tools MCP, que não são idempotentes, pelo mesmo motivo do ADR-0020.

**Modelo reserva.** `fallback_models` tem até dois modelos da matriz, usados em `on_error` e em `on_rate_limit` na ordem dada. A validação na escrita exige que:

- a reserva seja diferente do modelo principal;
- a reserva tenha as capabilities que o agente liga (visão, pensamento estendido, saída estruturada).

Com isso, a troca não muda o que o agente sabe fazer.

**O custo segue o modelo que respondeu.** O tracking passa a somar o custo por modelo a partir de `RunMetrics.details`. Quando o provedor não informa custo, a estimativa (ADR-0021) usa a tabela de preço de cada modelo, e o run guarda qual modelo respondeu. O medidor que embrulha o modelo também embrulha as reservas.

**Saída estruturada por JSON Schema.** `output_schema` no payload é validado na escrita:

- o JSON Schema precisa ser válido;
- a raiz é `object`, e o schema tem no máximo 32 KB;
- o modelo e as reservas precisam ter a capability `structured_output`.

A caixa "Saída estruturada" deixa de ser uma flag solta: ela fica ligada sempre que há schema. A suíte ganha a checagem `schema`, em que a resposta precisa validar contra o JSON Schema da versão testada.

**No modo de demonstração**, com o modelo de replay, o retry e a reserva não se aplicam. O schema vale, e a resposta gravada precisa ser JSON.

## Alternativas descartadas

- **`Agent.retries`.** É o retry mais simples de ligar, mas repete o run inteiro com as tools. Uma tool MCP que fez um estorno seria chamada de novo.
- **Limite de custo em dólar por run.** Exigiria somar o custo a cada chamada de modelo dentro do run e interromper no meio. O limite de tools corta a causa comum, o laço, sem medir no meio do run.
- **Schema como classe Pydantic gerada.** Daria `parser_model` para modelo sem saída estruturada nativa. Mas o Agno não usa `parser_model` com schema em `dict` (`agent/_messages.py:1198`), e gerar classe a partir do schema do usuário seria executar estrutura arbitrária. A capability na matriz já filtra os modelos.
- **Reserva da instância, não do agente.** Um agente com visão não pode cair num modelo sem visão. A escolha tem que ser por agente, validada contra as capabilities dele.

## Consequências

- Um laço de tool para no limite. Cada chamada além dele volta ao modelo como erro de limite, sem executar, e o modelo responde com o que já tinha. A árvore de execução mostra as chamadas que rodaram.
- Um 429 passageiro deixa de virar falha, e o pico de erro cai junto. A reserva custa o preço dela, e o analytics passa a separar o consumo por modelo.
- Com a reserva, a resposta pode vir de outro provedor, com outro estilo. A suíte agendada (ADR-0016) roda com o principal. A reserva entra na mesma suíte quando o agente é testado com o principal fora do ar, e isso fica a cargo de quem configura.
- A integração recebe JSON validado pelo provedor e pela suíte. Mudar o schema é mudar o contrato com quem integra, e o diff da versão mostra isso.
- Nenhuma migration: tudo fica no payload versionado.

## O que me faria reverter

Se o Agno passar a oferecer retry de tool marcado como idempotente, o retry do run volta a ser opção. Se a saída estruturada nativa falhar com frequência em algum provedor, o `parser_model` com uma classe fixa por caso de uso substitui o schema livre.
