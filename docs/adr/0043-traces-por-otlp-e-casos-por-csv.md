# ADR-0043 — Traces por OTLP e casos de teste por CSV

**Status:** Aceito
**Data:** 2026-11-12

## Contexto

Duas lacunas para quem opera a plataforma junto com o resto da empresa.

**Traces.** O AgentOS grava os spans de cada execução no banco da instância (`setup_tracing_for_os`, com o `AgnoInstrumentor` do OpenInference), e o painel monta a árvore de execução a partir deles. Quem já tem Datadog, Grafana Tempo ou Honeycomb quer ver o agente na mesma ferramenta em que vê o resto do sistema, com alerta e retenção dela. O provider do OpenTelemetry é global por processo e é criado pelo AgentOS no construtor.

**Casos de teste.** A suíte (ADR-0015) recebe caso a caso pelo formulário, por sugestão de conversa ou em lote a partir das conversas (ADR-0038). Quem já tem um roteiro de perguntas numa planilha, ou quer revisar a suíte fora do painel, precisa digitar tudo de novo.

## Decisão

**OTLP como segundo destino dos mesmos spans.** Com `OTEL_EXPORT_ENABLED=true`, a API acrescenta ao `TracerProvider` do AgentOS um `BatchSpanProcessor` com o exportador OTLP por HTTP (`opentelemetry-exporter-otlp-proto-http`). Endpoint e cabeçalhos vêm das variáveis padrão do OpenTelemetry (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`), que é como os três fornecedores documentam a configuração. O banco continua recebendo tudo, e a árvore do painel não muda.

- **Conteúdo fora por padrão.** Antes de sair, o span passa por um filtro que remove os atributos com o texto da conversa: `input.value`, `output.value`, mensagens do modelo (`llm.input_messages.*`, `llm.output_messages.*`), parâmetros e resultado de tool. Ficam nome, duração, status, modelo, tokens e ids. `OTEL_EXPORT_CONTENT=true` libera o conteúdo para quem decidiu mandar a conversa ao fornecedor.
- **Recurso com nome.** Os spans saem com `service.name` de `OTEL_SERVICE_NAME` (padrão `automata-api`).
- **Uma vez por processo.** O provider é global; o processador entra uma vez, mesmo com vários apps no mesmo processo (testes).
- **Sem tracing, sem exportação.** Com `TRACING_ENABLED=false` não há spans; a API avisa no log.
- **Fora do `guarded_client`.** O endpoint é configurado por quem opera a instância, no ambiente, como o SMTP; não vem do painel.

**CSV com uma linha por caso.** `POST /api/v1/configs/{id}/eval-cases/import` recebe o arquivo (até 512 KB) e `GET .../eval-cases/export` devolve a suíte no mesmo formato, para ida e volta. Colunas:

| Coluna | Vira |
|---|---|
| `nome`, `mensagem` | nome e entrada do caso (obrigatórios) |
| `contexto` | turnos anteriores, um por linha da célula |
| `contem`, `nao_contem`, `comeca_com` | checagem de texto; vários valores separados por `|` |
| `tools` | tools que precisam ser chamadas, separadas por `|` |
| `criterio`, `nota_minima` | juiz; com nota, modo numérico |
| `bloqueio` | `sim` ou a regra esperada |
| `etapas` | etapas do workflow que precisam rodar, separadas por `|` |
| `outras` | checagens sem coluna própria, em JSON (a exportação usa para não perder nada) |

O separador de colunas é `,` ou `;`, detectado no cabeçalho, porque o Excel em português salva com `;`; por isso as listas dentro da célula usam `|`. O arquivo pode vir em UTF-8 ou Windows-1252. Cada linha passa pela mesma validação do formulário (`EvalCaseInput` e a checagem por tipo de config). A importação é tudo ou nada: com `dry_run=true` devolve o relatório por linha sem gravar; sem ele, grava só se nenhuma linha tiver erro, respeitando o máximo de 50 casos e o nome único. O painel mostra a prévia e só então confirma.

## Alternativas descartadas

- **Trocar o exportador do banco pelo OTLP.** A árvore do painel e o histórico por run dependem do banco.
- **Collector embutido.** Mais um serviço para operar; quem quer collector aponta o endpoint para o dele.
- **gRPC.** Traz `grpcio`, pesado para a imagem; os três fornecedores aceitam OTLP por HTTP.
- **Importação linha a linha com gravação parcial.** Metade de uma suíte importada é pior que nenhuma: o gate passaria a valer com casos faltando.
- **JSON em vez de CSV.** A planilha é onde esses roteiros já vivem; JSON é o formato da API, que já aceita caso a caso.

## Consequências

- Uma dependência nova na API (exportador OTLP por HTTP).
- Com o conteúdo liberado, a conversa sai da instância para o fornecedor de observabilidade, com a retenção dele.
- O CSV é um formato a mais para manter compatível com as checagens; checagem nova precisa de coluna.
