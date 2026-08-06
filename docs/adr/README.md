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
| [0009](0009-superficie-de-integracao.md) | MCP server mode e REST como superfície de integração | Proposto |
