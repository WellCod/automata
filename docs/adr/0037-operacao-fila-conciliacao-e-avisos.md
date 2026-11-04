# ADR-0037 — Operação: painel da fila, retry por agente idempotente, conciliação de custo e aviso por e-mail

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-04

## Contexto

O backlog de operação ficou espalhado em três ADRs:

- **A fila durável (ADR-0020) não aparece no painel.** Um run em background que falhou fica na tabela de jobs do Agno, e só quem lê o banco sabe. O ADR-0020 também deixou para depois o retry de agente marcado como idempotente: a fila roda uma tentativa só, porque uma tool com efeito não pode repetir sozinha.
- **O custo é estimado pela tabela de preços (ADR-0021).** Anthropic e OpenAI não devolvem custo na resposta, mas têm relatório de custo por dia na API de administração. Hoje ninguém confere se a estimativa bate com a fatura.
- **Aviso só por webhook (ADR-0018 e ADR-0021).** Quem não tem um canal com webhook não recebe aviso nenhum.

Verificado no Agno 3.1.8 e na documentação dos provedores:

- A tabela de jobs (`ai.agno_jobs`) grava `component_type`, `component_id`, `status`, `attempt`, `max_attempts`, `error` e as datas. `PostgresDb.list_jobs(status=..., limit, page)` lista os jobs. `PostgresDb.requeue_job(job_id)` dá mais uma tentativa a um job que falhou ou foi cancelado, subindo `max_attempts` para `attempt + 1`. O AgentOS expõe `/queue/jobs` com o scope dele.
- **Anthropic:** `GET /v1/organizations/cost_report`, com chave Admin (`sk-ant-admin...`) no `x-api-key` e `anthropic-version`. Os buckets são só diários (`1d`), até 31 por página, com `has_more` e `next_page`. O valor vem em `results[].amount`, em **centavos**, como string decimal. Com `group_by[]=description`, vem também `results[].model`. O endpoint não está no SDK, só por HTTP.
- **OpenAI:** `GET /v1/organization/costs?start_time=<unix>&bucket_width=1d`, com chave admin no `Authorization: Bearer`. O valor vem em `results[].amount.value`, em **dólares**, e a paginação usa `has_more` e `next_page`.

## Decisão

**Painel da fila.** Rotas próprias, só para o owner (scope `queue:admin`):

- `GET /api/v1/queue`: contagem por situação, o job na fila há mais tempo e os últimos 50 jobs, com o nome do agente ou time;
- `POST /api/v1/queue/jobs/{id}/requeue`: chama o `requeue_job` do Agno e registra quem pediu.

As rotas leem a tabela pelo `PostgresDb` do app. Com a fila em memória (`BACKGROUND_QUEUE_DURABLE=false`), elas respondem que a fila durável está desligada.

**Retry por agente marcado como idempotente.** A seção `run` (ADR-0027) ganha `background_retries`, de 0 a 2 e 0 por padrão, no agente e no time. Ligar é declarar que repetir o run inteiro é seguro, e o painel avisa disso. O poller de avisos dá requeue em job que falhou de config com `background_retries > 0` e `attempt <= background_retries`. Um job que falha de vez, sem retry ou com os retries esgotados, gera o evento `job.failed` nos destinos de aviso, uma vez por job.

**Conciliação de custo.** Com `ANTHROPIC_ADMIN_KEY` ou `OPENAI_ADMIN_KEY` no ambiente, o poller busca uma vez por hora o custo dos últimos 3 dias de cada provedor e grava em `provider_cost`, com provedor, dia, valor informado e hora da leitura (migration 0047). `GET /api/v1/metrics/reconciliation?days=30` compara, por dia e provedor:

- o informado;
- o estimado pelo Automata, que é o `usage_event` mais o consumo de embedding dos modelos daquele provedor;
- a diferença, em dólares e em percentual.

O Analytics mostra a comparação. A divergência acima de `RECONCILIATION_ALERT_PERCENT` (20 por padrão) num dia fechado gera `cost.divergence`.

**Aviso por e-mail.** O destino de aviso ganha `kind`, que pode ser `webhook` (como hoje) ou `email`. O e-mail tem até 5 endereços (migration 0048). O envio usa `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` e `SMTP_STARTTLS`. Sem `SMTP_HOST`, o painel não oferece o tipo. O texto do e-mail é o mesmo do webhook. O teste do destino manda um e-mail de teste.

## Alternativas descartadas

- **Usar o `/queue` do AgentOS direto no painel.** Ele exige o scope do AgentOS e não sabe o nome do agente. As rotas próprias seguem o mesmo padrão de autorização das outras telas do owner.
- **Retry automático para todo agente.** Repetir sozinho um run que pagou um boleto por tool seria o pior erro possível. A declaração é por agente.
- **Corrigir o custo estimado com o informado.** O relatório do provedor é da organização inteira, que pode ter outros sistemas na mesma chave. Ele serve para conferir, não para atribuir por agente.

## Consequências

- A chave admin do provedor é poderosa. Ela fica só no ambiente da API e é usada só para leitura dos relatórios.
- A conciliação só bate se a chave do provedor for exclusiva da instância. O painel deixa isso dito ao lado do número.
- Um e-mail de aviso sai pelo SMTP da empresa, com o texto do evento e sem dado de conversa.
