# ADR-0041 — Trilha de auditoria

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-10

## Contexto

O painel muda o comportamento de produção: publica versão, faz rollback, liga canário, muda o piso de guardrails, emite token de integração, apaga os dados de um titular, troca o papel de um usuário. Hoje só sobra rastro disso no log estruturado da Fase 6, que não tem quem fez, roda fora do banco e some com o container. A pergunta "quem mudou o prompt do atendimento na sexta?" só tem resposta pelo `author` da versão, e o resto das ações não tem nenhuma.

O que existe e serve:

- Toda escrita do painel e dos tokens passa pelas rotas próprias em `/api/v1`, montadas dentro do AgentOS, que já põe `user_id` e `scopes` em `request.state`.
- A decisão humana numa aprovação passa pelas rotas de `continue` do AgentOS (`/agents|teams|workflows/{id}/runs/{run_id}/continue`).
- O `RequestIDMiddleware` já dá um `request_id` por requisição, que liga a trilha ao log.

## Decisão

**Tabela `audit_event`** (migration 0055): `created_at`, `actor` (id do usuário do painel ou `integration:<id>`), `action` (método e rota modelo, como `POST /api/v1/configs/{config_id}/publish`), `config_id` quando a rota tem um, `params` (os outros parâmetros do path), `status_code`, `ip` (do mesmo cabeçalho confiável do rate limit), `request_id` e `detail` opcional com o antes e o depois. Índices por `created_at`, `(actor, created_at)` e `(config_id, created_at)`.

**Middleware no app externo.** Depois da resposta, grava toda requisição `POST`, `PUT`, `PATCH` e `DELETE` em `/api/v1` e o `continue` das aprovações, inclusive as recusadas com 4xx (tentativa negada também é informação). Ficam de fora o login (já no log, e sem autor antes de autenticar), o webhook público das origens (sem autor humano) e os `POST` que só leem: busca de teste, comparação de busca, prévia de corte e linter. O corpo da requisição nunca é gravado: tem prompt, segredo e dado pessoal. A gravação roda fora do event loop e uma falha nela vira log de erro, nunca erro da requisição.

**Antes e depois** nas ações que mudam produção, preenchido pela própria rota em `request.state.audit_detail`: publicação e rollback (versão vigente antes e depois), canário (versão e percentual), piso da instância (regras antes e depois), papel e ativação de usuário, orçamento por config e por quem chama. As outras ações ficam só com rota, alvo e resultado.

**Leitura** em `GET /api/v1/audit`, só owner (scope `audit:read`), com filtros por quem, config, ação e período e paginação por cursor (`created_at`, `id`) de até 100 por página. O painel ganha a página **Auditoria** em Administração e o histórico de ações na aba Versões do agente.

**Retenção** de 365 dias por padrão (`AUDIT_RETENTION_DAYS`), apagada pelo poller de avisos uma vez por dia.

**Titular.** O id do titular entra no path das rotas de titular. A exclusão (ADR-0032) troca esse id pelo pseudônimo também em `audit_event`, como faz no consumo e nos runs.

## Alternativas descartadas

- **Gravar em cada rota.** Mais de 60 rotas de escrita; uma esquecida some da trilha sem ninguém notar. O middleware pega todas, e as rotas só complementam com o antes e o depois.
- **Gravar o corpo da requisição.** Leva prompt, segredo de conector e dado pessoal para uma tabela que fica um ano.
- **Trilha imutável com hash encadeado.** Protege contra quem tem acesso ao banco, que também tem a chave dos segredos. Fica como gatilho de revisão se alguma norma exigir.
- **Auditar as rotas do runtime (runs).** Já estão em `agent_run`, com quem chamou.

## Consequências

- Toda escrita ganha um `INSERT` depois da resposta. O volume é o das ações do painel, não o das conversas.
- O owner vê quem fez o quê, mas não o conteúdo: para o prompt, a versão continua sendo a fonte.
- Revisitar quando entrar SSO: o `actor` passa a vir do provedor de identidade.
