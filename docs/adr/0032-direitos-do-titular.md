# ADR-0032 — Direitos do titular: consulta, exportação e exclusão por usuário, e máscara com padrões próprios

**Status:** Aceito
**Data:** 2026-11-04

## Contexto

A instância guarda dado de pessoas em muitos lugares: a conversa (sessões e runs do Agno), a memória do usuário (ADR-0025), as aprovações pendentes, os traces, o registro de revisões (ADR-0028), os trechos retirados (ADR-0030) e o consumo. Hoje dá para apagar as memórias de alguém (ADR-0025), mas não dá para responder ao pedido que a LGPD garante ao titular:

- confirmar se há dado dele e dizer o que há;
- entregar uma cópia;
- apagar.

O titular é o `user_id` do run: o usuário do painel ou o id que o sistema integrado manda (ADR-0025).

A máscara de dados pessoais (ADR-0013) conhece CPF, CNPJ, cartão, e-mail e telefone. Matrícula, número de contrato e protocolo de cada empresa passam inteiros para o modelo, para a memória e para o registro.

Verificado no Agno 3.1.8 instalado:

- `get_sessions(user_id=...)` lista as sessões de um usuário, e `delete_session` apaga a sessão com os runs e as transcrições dela (`db/postgres/postgres.py:1401`).
- `get_user_memories(user_id=...)` e `delete_user_memories(ids, user_id=...)` cobrem a memória.
- Também guardam `user_id` as tabelas `agno_approvals`, `agno_tool_results`, `agno_traces`, `agno_jobs`, `agno_eval_runs`, `agno_learnings` e `agno_metrics`. Os spans (`agno_spans`) ficam ligados ao trace. Não há método de exclusão por usuário para todas elas.
- Do lado do projeto, `agent_run` e `usage_event` guardam o `user_id`. `agent_run` também guarda conteúdo da conversa em `review_log`, `screened_tools` e `block_detail`.

## Decisão

**Consulta e exportação.** O owner (scope `data_subjects:admin`) usa estas rotas:

- `GET /api/v1/data-subjects/{user_id}` conta o que existe: conversas, runs, memórias, aprovações, traces e o consumo do mês.
- `POST /api/v1/data-subjects/{user_id}/export` gera em background um JSON com as sessões e runs, as memórias, as aprovações, os runs registrados pelo projeto e o consumo. O JSON fica compactado na tabela `data_subject_request` (migration 0042) por 7 dias.
- `GET /api/v1/data-subject-requests` lista os pedidos, e `GET .../{id}/download` baixa o arquivo enquanto ele valer.

**Exclusão.** `POST /api/v1/data-subjects/{user_id}/erase` exige que o corpo repita o `user_id`, para não apagar por engano. Em background, a exclusão:

- apaga por SQL, numa transação, as sessões com os runs, as transcrições e as compactações delas, na ordem que o `delete_session` do Agno usa. O Agno não tem exclusão por usuário para todas as tabelas, e uma transação só evita deixar o titular pela metade;
- apaga, com o `user_id`, as memórias, as aprovações, os resultados de tool, os traces (com os spans deles), os jobs da fila, os runs de suíte, os aprendizados e as métricas do Agno;
- troca o `user_id` em `agent_run` e `usage_event` por `apagado:` mais os primeiros 16 caracteres do sha256 dele, e limpa `review_log`, `screened_tools` e `block_detail`. Contagem, latência e custo continuam batendo nas métricas e no orçamento;
- tira a ligação (`source_run_id`) dos casos de teste criados de conversas dele (ADR-0016). O texto do caso já foi mascarado na criação;
- remove o orçamento por quem chama (ADR-0031) daquele `user_id`.

O pedido fica em `data_subject_request` com o hash no lugar do id, quem pediu, quando e quantas linhas saíram de cada lugar. O pedido de exportação também guarda só o hash depois que o arquivo vence.

**Padrões próprios na máscara.** `guardrails.pii.custom` aceita até 10 padrões por agente, cada um com:

- o rótulo, que vira "[<rótulo> removido]";
- o prefixo opcional, até 10 letras, dígitos ou `-`;
- a quantidade mínima e máxima de dígitos, de 4 a 20.

O padrão vira um regex montado pelo código, sem regex livre do usuário. Um regex livre traria de volta o risco do incidente da Fase 28, porque o `re` segura o GIL. Valem os mesmos lugares da máscara do agente: a entrada (mascarar ou bloquear), a memória do usuário e o guardrail de saída.

## Alternativas descartadas

- **Apagar `agent_run` e `usage_event` do titular.** As métricas, o custo do mês e o orçamento do agente mudariam para trás. O hash tira a pessoa e mantém o número.
- **Exportação síncrona.** Um titular com meses de conversa gera um arquivo grande. Em background, o pedido não segura a request.
- **Regex livre na máscara.** É flexível, mas um padrão ruim trava a API, e quem configura o agente não é quem responde pelo incidente.

## Consequências

- A exclusão não alcança backups do banco nem cópias que o sistema integrado tenha feito. Isso fica registrado para quem opera a instância.
- O arquivo exportado é dado pessoal guardado por 7 dias no banco. Só o owner baixa, e o arquivo some no vencimento.
- Um `user_id` reaproveitado depois da exclusão começa do zero. O consumo antigo fica com o hash.
- Pedido feito pelo próprio titular, prazo legal com alerta e exclusão em backups ficam para depois.
