# Architecture Decision Records

Registro das decisões de arquitetura do Automata. Uma decisão por arquivo, numerada, imutável depois de aceita.

Se uma decisão mudar, **não edite o ADR** — crie um novo que a substitui e marque o antigo como `Substituído por ADR-XXXX`. O valor do registro está em mostrar como o raciocínio evoluiu, não em parecer que sempre esteve certo.

## Formato

Cada ADR tem cinco seções:

- **Contexto** — qual era o problema e o que estava em jogo
- **Decisão** — o que foi escolhido, em uma frase
- **Alternativas descartadas** — e o motivo específico, não "era pior"
- **Consequências** — o que isso me obriga a fazer, inclusive o que ficou pior
- **O que me faria reverter** — o gatilho concreto para reabrir a decisão

A última seção é a que importa mais. Decisão sem critério de reversão é opinião.

## Status

- `Aceito` — decidido e em vigor
- `Proposto` — escrito, ainda não confirmado
- `Substituído` — trocado por um ADR posterior

## Índice

| # | Decisão | Status |
|---|---|---|
| [0001](0001-monorepo.md) | Monorepo em vez de repositórios separados | Aceito |
| [0002](0002-config-em-banco-proprio.md) | Config de agente em banco próprio, não no Studio | Aceito |
| [0003](0003-single-tenant.md) | Deploy single-tenant, uma instância por cliente | Aceito |
| [0004](0004-painel-proprio.md) | Painel próprio; Control Plane só como ferramenta interna | Aceito |
| [0005](0005-auth-jwt-proprio.md) | JWT assimétrico emitido pelo backend, com BFF no Next | Aceito |
| [0006](0006-instructions-agnosticas-de-provider.md) | Instructions agnósticas de provider | Aceito |
| [0007](0007-licenciamento.md) | Código aberto sob AGPL-3.0 com licença comercial paralela | Proposto |
| [0008](0008-demo-com-respostas-gravadas.md) | Demo pública com respostas gravadas | Proposto |
| [0009](0009-superficie-de-integracao.md) | MCP server mode e REST como superfície de integração | Aceito |
| [0010](0010-servidores-mcp-externos.md) | Servidores MCP externos como cadastro operacional, segredo cifrado e só HTTP | Aceito |
| [0011](0011-times-versionados.md) | Times multi-agente na mesma tabela de configs, membros por referência | Aceito |
| [0012](0012-bases-de-conhecimento.md) | Bases de conhecimento como cadastro próprio, pgvector e embeddings da Voyage | Aceito |
| [0013](0013-guardrails-por-agente.md) | Guardrails por agente, versionados no payload, com regras brasileiras próprias | Aceito |
| [0014](0014-workflows-por-etapas.md) | Workflows por etapas sobre agentes e times publicados, com regras próprias no lugar de CEL | Aceito |
| [0015](0015-evals-por-agente.md) | Evals por agente no painel, com casos fora da versão e o runner de suíte do Agno | Aceito |
| [0016](0016-evals-continuos.md) | Evals contínuos: disparo por token de integração, agendamento próprio e casos a partir de conversas reais | Aceito |
| [0017](0017-estrategia-de-recuperacao.md) | Estratégia de recuperação por base com o reranker do Agno e HyDE medido | Aceito |
| [0018](0018-avisos-de-regressao.md) | Avisos de regressão da suíte agendada por webhook assinado, só nas mudanças de estado | Aceito |
| [0019](0019-compactacao-de-conversa.md) | Compactação de conversa por agente, versionada no payload, com limite baixo | Aceito |
| [0020](0020-fila-duravel.md) | Fila durável do Agno para runs em background, no Postgres, com Redis opcional | Aceito |
| [0021](0021-orcamento-e-alertas.md) | Custo pela tabela de preços, orçamento mensal por config e destinos de aviso | Aceito |
| [0022](0022-suite-de-workflow-e-bloqueio.md) | Suíte de testes para workflows e caso que espera bloqueio de guardrail | Aceito |
| [0023](0023-revisao-humana-no-workflow.md) | Revisão humana numa etapa do workflow, antes de rodar ou depois da saída | Aceito |
| [0024](0024-conectores-de-conhecimento.md) | Conectores de conhecimento (GitHub, S3, SharePoint) e reindexação agendada | Aceito |
| [0025](0025-memoria-do-usuario.md) | Memória do usuário entre sessões, por agente, com retenção, PII mascarado e exclusão | Aceito |
| [0026](0026-rotacao-de-chaves.md) | Rotação da chave JWT e da chave dos segredos com uma chave anterior aceita na leitura | Aceito |
| [0027](0027-controle-do-run.md) | Controle do run: limite de tools, retry do provedor com modelo reserva e saída estruturada | Aceito |
| [0028](0028-revisao-humana-completa.md) | Revisão humana completa: saída editada, revisão por volta de laço e registro das decisões | Proposto |
