# ADR-0040 — Liberação gradual de versão

**Status:** Aceito
**Data:** 2026-11-10

## Contexto

Publicar troca a versão vigente para 100% das conversas de uma vez (ADR-0002). A suíte (ADR-0015) e o gate pegam o que os casos cobrem, mas não o que só aparece com tráfego real: uma pergunta que ninguém escreveu como caso, um custo por conversa que dobra, uma latência que sobe com o modelo novo. Quando isso aparece, já está em todas as conversas, e o caminho é o rollback.

O que existe e serve:

- O `AgentFactory` do Agno monta o agente a cada request a partir de um `RequestContext`, que traz o `session_id` da conversa.
- `load_version` já escolhe a versão pela vigente ou pela pedida no modo teste.
- `agent_run` e `usage_event` registram cada run com custo, duração e status, mas não guardam **qual versão** respondeu.

## Decisão

**Canário por config.** `agent_config` ganha `canary_version_id`, `canary_percent` (1 a 50) e `canary_started_at` (migration 0054). Com canário ligado, a conversa sem versão pedida cai na versão do canário quando `sha256(config_id:session_id) mod 100 < canary_percent`. A escolha é pela sessão, então uma conversa não troca de versão no meio. Sem `session_id`, o sorteio é por run. O modo teste continua escolhendo a versão.

Vale para agente e para o líder do time. Os membros do time seguem a vigente deles (ou a versão fixada), e o workflow fica de fora nesta fase: cada etapa já é um agente com a própria liberação.

**Versão no run.** `agent_run.version_id` grava a versão que respondeu, com índice `(version_id, created_at)`. É o que permite comparar e auditar depois.

**Rotas** (`/api/v1/configs/{id}/canary`, scope `configs:publish`):

- `POST` liga o canário com `percent`. Sem `version_id`, publica o rascunho como versão nova sem mover a vigente, com o mesmo gate da publicação (`require_passing_evals`). Com `version_id`, usa uma versão já publicada do config.
- `GET` compara a vigente e o canário desde `canary_started_at`: runs, taxa de erro, p50 e p95 de duração, custo médio por run e o resultado da última suíte de cada versão.
- `POST .../promote` move a vigente para o canário e desliga o canário.
- `DELETE` desliga o canário; as conversas voltam todas para a vigente.

Publicar ou fazer rollback com canário ligado desliga o canário, para não sobrar uma versão velha recebendo tráfego.

## Alternativas descartadas

- **Sorteio por run.** A conversa trocaria de prompt e de modelo no meio, e a comparação misturaria as duas versões no mesmo histórico.
- **Promoção automática por métrica.** Taxa de erro e custo com poucas dezenas de runs são ruído. A decisão fica com quem opera, olhando a comparação.
- **Canário no workflow.** As etapas já são agentes com a própria versão; um canário do workflow inteiro dobraria as combinações.

## Consequências

- Durante o canário, duas versões respondem ao mesmo tempo. Os números do agente (desempenho, orçamento) somam as duas; a comparação separa.
- Conversas antigas, de antes do canário, não têm `version_id` e ficam fora da comparação.
- O percentual tem teto de 50%: acima disso, é publicar.
