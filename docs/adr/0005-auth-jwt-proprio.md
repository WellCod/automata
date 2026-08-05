# ADR-0005 — JWT assimétrico emitido pelo backend, com BFF no Next

**Status:** Aceito
**Data:** 2026-08-05

## Contexto

O AgentOS valida JWT em toda request e confere os scopes do token contra a permissão exigida por endpoint. Scopes têm granularidade por recurso e por instância — por exemplo `agents:read` e `agents:<id>:run`. O token pode ser emitido pelo Control Plane ou pelo próprio backend, no modo self-hosted.

O painel é entregue ao cliente final e precisa de autenticação e papéis próprios.

## Decisão

O backend emite JWT assinado com par de chaves assimétrico (RS256) e o AgentOS verifica com a chave pública — modo BYO token. Todo acesso do browser passa por Route Handlers do Next agindo como BFF; a chave de assinatura nunca sai do servidor.

`user_isolation` habilitado para escopar sessions, memories e traces por usuário.

## Alternativas descartadas

**JWT emitido pelo Control Plane.** Implica conta Agno por usuário do cliente e papéis geridos pela Agno. Incompatível com produto white-label — ver ADR-0004.

**Segredo compartilhado (HS256).** Funciona e é mais simples, mas com uma instância por cliente o número de segredos a rotacionar cresce, e a mesma chave assina e verifica. Assimétrico permite que o verificador nunca possua capacidade de emissão.

**Token no client, como faz o `agent-ui`.** O template usa um único bearer token, possivelmente via `NEXT_PUBLIC_*`. No Next.js esse prefixo é embutido no bundle e chega ao browser. Token exposto no client é token vazado — isso é restrição, não convenção.

## Consequências

- Nenhuma chamada do componente client vai direto ao AgentOS. Ele chama `/api/...` do próprio Next, que injeta o Bearer e repassa. Uma camada extra de latência, aceita.
- Chave privada carregada de variável de ambiente ou secret manager, nunca de arquivo commitado.
- A tabela de scopes usada precisa estar documentada no README, com o endpoint que cada um libera.
- Teste automatizado varre o bundle client em busca de nomes de variável sensíveis e falha se encontrar. Sem isso a regra depende de disciplina.
- Rotação de chave exige coordenação entre emissor e verificador na mesma instância.
- Papéis e usuários são modelo nosso, não herdado. Mais código, mas é requisito de white-label.

## O que me faria reverter

Se o cliente exigir SSO corporativo com o IdP dele — Entra ID, Okta, Google Workspace. Nesse caso o emissor passa a ser o IdP do cliente e nosso backend só verifica, o que na verdade **simplifica** o desenho: some a responsabilidade de emitir e guardar chave privada.

Isso é reversão provável, não hipotética: cliente enterprise costuma exigir SSO. O desenho atual não impede — só troca quem assina. Vale não acoplar lógica de negócio ao formato do nosso token para manter essa porta aberta.
