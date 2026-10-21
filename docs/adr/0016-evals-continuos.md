# ADR-0016 — Evals contínuos: disparo por token de integração, agendamento próprio e casos a partir de conversas reais

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-10-21

## Contexto

A suíte da Fase 16 (ADR-0015) só roda quando alguém clica em Rodar. Ela pega regressão na mudança de configuração, mas não no que muda por fora: o provedor atualiza o modelo, uma base de conhecimento é reindexada, um servidor MCP muda o formato da resposta, um membro de time ganha versão nova. O próprio ADR-0015 registrou isso como consequência e deixou o agendamento para depois.

Também ficaram de fora dois caminhos que fazem a suíte crescer e ser usada:

- **CI de quem consome o agente.** O sistema que chama o agente por REST ou MCP muda no ritmo dele e quer saber, no próprio pipeline, se o agente ainda responde como esperado.
- **Casos a partir de conversas reais.** Escrever caso do zero é o que trava a suíte. A conversa que deu errado em produção é o melhor caso de regressão, e hoje precisa ser copiada à mão.

Verificado no Agno 3.1.8 instalado (a atualização entra antes desta fase) e no código atual:

- **Scheduler do AgentOS** (`agno.scheduler`, `AgentOS(scheduler=True)`):
  - guarda os agendamentos numa tabela do banco do Agno (`agno_schedules`) e expõe `/schedules` no AgentOS;
  - um poller reivindica o que venceu (`claim_due_schedule`) e um executor faz uma **chamada HTTP** ao próprio servidor, autenticada com um `internal_service_token`;
  - na v3, esse token recebe só `agents`, `teams` e `workflows` (`read` e `run`) e `schedules:read`, sem os escopos das rotas próprias;
  - o agendamento ganhou `user_id` e um vínculo de origem (`managed_by`, `target_type`, `target_id`), mas o alvo só pode ser um run de agente, time ou workflow, e o executor recusa e desliga o agendamento cujo endpoint não bate com esse alvo;
  - agendamento sem cron roda só pela rota de disparo (3.1.5);
  - `agno.scheduler.cron` tem `validate_cron_expr`, `validate_timezone`, `compute_next_run` e `next_run_for`, sobre `croniter` e `pytz`, que já vêm com `agno[os]`.
- **Runner de suíte na v3** (3.1.6): o `Case` aceita `session_id`, `user_id`, `session_state` e `metadata`, repassados ao run. O `setup` roda antes do caso, fora do timeout, e casos com o mesmo `session_id` continuam a mesma sessão. Isso permite avaliar um turno com os turnos anteriores já na conversa. O `user_id` do caso dispensa a troca de usuário que a Fase 16 faz pela `ContextVar`.
- **Tokens de integração** (ADR-0009): JWT com `jti`, revogáveis, com escopos por recurso (`agents:<id>:run`, `teams:<id>:run`) e nada de configuração. As rotas próprias checam escopo com `require_scopes`, sem noção de recurso.
- **Conversa de um run:** `agent_run` guarda `run_id` e `session_id`, não o texto. Na v3, cada run é uma linha de `agno_runs`, lida direto por `db.get_run(run_id)`, com entrada, saída e tools chamadas, e existe com ou sem tracing. Os turnos anteriores saem de `db.get_runs(session_id=...)`. O trace (`/runs/{id}/trace`) só é liberado ao dono da conversa ou a admin.
- **Dados pessoais:** `app.guardrails.pii` tem `find_pii` e `mask` para CPF, CNPJ, cartão, e-mail e telefone.

## Decisão

**Toda execução ganha origem e alvo por apelido.** O `eval_run` passa a registrar `trigger` (`manual`, `integration`, `schedule`) e quem disparou. Além de `version_id`, a criação aceita `target`: `draft` ou `current`. Quem está de fora não conhece ids de versão, e o agendamento precisa seguir a vigente mesmo depois de uma publicação.

**Token de integração pode disparar e consultar a suíte de configs escolhidos.** Na emissão, o owner marca para quais agentes e times o token pode rodar a suíte. O token ganha `evals:<id>:run` e `evals:<id>:read` só para esses. As rotas de execução passam a aceitar o escopo global (papel editor) **ou** o escopo do recurso do path, numa dependência própria (`require_resource_scope`). O token não cria nem edita casos, não troca o gate e não publica. O resumo da execução ganha `verdict` (`passed`, `failed`, `pending`) para o pipeline decidir sem interpretar contagens. A documentação traz um exemplo de job de CI com `curl` e polling.

**Agendamento com poller próprio, não o scheduler do AgentOS.** Uma tabela `eval_schedule`, um por config, com expressão cron, fuso, alvo (`current` por padrão), modelo do juiz e `next_run_at`. Um laço no lifespan da API acorda a cada minuto, reivindica o que venceu com `SELECT … FOR UPDATE SKIP LOCKED` e cria a execução direto, pelo mesmo caminho do botão Rodar, sem HTTP. A validação e o próximo horário usam `agno.scheduler.cron`. O painel oferece frequências prontas (a cada 6 h, diária, semanal, dias úteis) e cron livre como avançado. Intervalo mínimo de 1 hora. Se já houver execução em andamento, o agendamento pula e marca o motivo. No modo demo o poller fica desligado.

**Regressão agendada vira sinal no painel.** Cada execução agendada é comparada com a anterior do mesmo agendamento, com a comparação caso a caso da Fase 16. A lista de agentes e times e a aba Testes mostram o estado da suíte (verde, falhando, regrediu, sem execução). Avisos por webhook ou e-mail ficam para depois.

**Caso com turnos anteriores.** Um caso pode trazer até cinco mensagens de contexto antes da mensagem avaliada. Na execução, o `setup` do `Case` roda essas mensagens no mesmo `session_id`, com o mesmo agente, e só a resposta da última passa pelas checagens. O contexto conta no timeout do caso, porque roda dentro do mesmo limite, e o consumo dele entra no custo da execução. Sem contexto, o caso continua de uma mensagem, como na Fase 16.

**Caso a partir de conversa real, sempre revisado antes de salvar.** No histórico de execuções e na árvore de execução, um run de conversa ganha a ação "Virar caso de teste". A API lê o run em `agno_runs`, monta uma sugestão e não grava nada: entrada do usuário, até cinco mensagens anteriores da mesma sessão como contexto, checagem de tools com as tools que o run de fato chamou, `not_empty` e, se houver modelo de juiz, um critério de rascunho a partir da resposta original. O formulário de caso abre preenchido, e salvar usa o `POST` de casos que já existe, com `source_run_id` para registrar de onde veio.

- **Mesma regra do trace:** só o dono da conversa ou admin gera a sugestão, e o papel precisa de `evals:write`.
- **Dados pessoais mascarados sempre,** com todos os tipos, mesmo se o agente não tiver guardrail de PII. O caso fica num cadastro que outros editores veem, e a conversa original não.
- **Contexto mascarado do mesmo jeito.** As mensagens anteriores passam pela mesma máscara de PII, e o formulário mostra cada uma para o editor cortar o que não importa. Runs bloqueados, runs de eval e etapas de workflow não viram caso.

## Alternativas descartadas

- **Scheduler do AgentOS.** Funciona para disparar runs de agente, mas não para a suíte, e a v3 deixou isso mais claro. O executor chama a rota por HTTP com um token que só tem escopos de agents, teams e workflows. Liberar `evals:run` a um segredo gerado em memória daria acesso à suíte de tudo. O vínculo de origem da v3 (`target_type`, `target_id`) só aceita run de agente, time ou workflow, e o executor desliga o agendamento cujo endpoint não bate com o alvo. Um agendamento apontado para a rota da suíte ficaria sem esse controle. Os agendamentos ficam no banco do Agno, sem chave estrangeira para o `agent_config`: apagar o agente deixaria agendamento órfão. As funções de cron dele são reaproveitadas; o executor e o poller, não.
- **Cron do sistema ou do GitHub Actions chamando a API.** Tira o agendamento do produto. Quem opera o agente precisaria de acesso à infraestrutura para mudar um horário, e a instância single-tenant (ADR-0003) não teria o recurso por padrão.
- **Token de integração com `evals:run` global.** Um sistema consumidor passaria a gastar tokens na suíte de agentes que não usa. O escopo segue o mesmo recorte por recurso dos tokens de run.
- **Salvar o caso direto a partir do run, sem revisão.** A conversa traz contexto que não vale como regra (data, nome, número de pedido), e a resposta original nem sempre é a correta. Caso criado sem revisão gera suíte que falha por motivo errado.
- **Sugerir checagem de texto com trechos da resposta original.** Prende o teste à redação daquele dia, e qualquer mudança de prompt vira regressão falsa. A sugestão usa tools chamadas, que são objetivas, e deixa a parte de conteúdo para o juiz, com critério editável.

## Consequências

- A suíte passa a pegar mudança de fora da configuração: modelo do provedor, base reindexada, MCP e membros de time. Só pega no próximo horário, não no momento da mudança.
- Execução agendada tem custo recorrente de tokens. O intervalo mínimo de 1 hora, uma execução por config por vez e o custo de testes separado no analytics deixam isso visível e limitado. A aba Testes mostra o custo da última execução ao lado da frequência escolhida.
- O poller roda dentro da API. Com mais de uma réplica, o `SKIP LOCKED` evita execução dupla. Se a API ficar fora do ar no horário, a execução vencida roda na volta, uma vez só, sem acumular atrasos.
- Token com acesso à suíte pode gerar custo enquanto não for revogado. A emissão mostra isso, a execução registra qual token disparou e a rota recusa nova execução enquanto houver uma em andamento.
- A sugestão de caso depende do run guardado pelo Agno em `agno_runs`. Run apagado não gera sugestão, e a interface diz isso.
- Mascarar PII troca valores por rótulos (`[CPF removido]`, `[e-mail removido]`). Um caso que dependia do valor exato precisa ser ajustado à mão.
- Caso com contexto custa mais: cada mensagem anterior é um run do modelo. O limite de cinco mensagens e o timeout do caso seguram isso.
- O runner da suíte passa a depender de dois campos da v3 (`setup` e `session_id` do `Case`). Esta fase só começa depois da atualização para a 3.1.x.
- Duas migrations: origem e alvo no `eval_run`, `context` e `source_run_id` no `eval_case`; tabela `eval_schedule`.

## O que me faria reverter

- Precisar agendar mais do que a suíte (runs de agente, reindexação de base, relatórios). Nesse caso, um agendador geral vale mais que vários laços, e o scheduler do AgentOS volta à mesa se aceitar alvos próprios no vínculo de origem e escopos configuráveis para o token interno.
- Volume de execuções agendadas que a API não aguente junto com o tráfego de conversa. Nesse caso, a suíte vai para um worker separado, como já está previsto para a ingestão do RAG.
- Pedido de cliente para não guardar nenhum texto de conversa fora da sessão. Nesse caso, a sugestão de caso passa a exigir confirmação explícita, ou sai.
