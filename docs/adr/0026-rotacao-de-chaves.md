# ADR-0026 — Rotação da chave JWT e da chave dos segredos sem derrubar sessões nem integrações

**Status:** Aceito
**Data:** 2026-10-29

## Contexto

A instância depende de duas chaves:

- **O par RSA do JWT** (`JWT_PRIVATE_KEY` e `JWT_PUBLIC_KEY`). A API assina todo token com a chave privada: sessão do painel (1 hora) e token de integração (até 90 dias, `MAX_DAYS`). A pública verifica em quatro lugares: no `Authorization` do AgentOS, no `/mcp` (`app/mcp_auth.py`), nas rotas de `/api/v1/auth` e no proxy do painel (`web/src/proxy.ts`).
- **A chave Fernet dos segredos** (`MCP_SECRETS_KEY`). Ela cifra em repouso os headers dos servidores MCP, a URL e o segredo do webhook da suíte agendada, os destinos de alerta e as credenciais dos conectores de conhecimento.

Hoje as duas aceitam uma chave só. Trocar a do JWT invalida na hora todo token emitido, inclusive os de integração que estão configurados em outros sistemas. Trocar a dos segredos deixa todos os segredos ilegíveis. Isso cobra caro por uma rotação, e a ação manual da Fase 11 (gerar par JWT novo depois do vazamento no histórico público) está parada desde 2026-10-15.

O ADR-0010 já previa que rotacionar a chave dos segredos "exige re-cifrar (comando próprio)". Esse comando nunca foi escrito.

Verificado no código e nas dependências:

- O `Authorization` do Agno 3.1.8 recebe `verification_keys` como lista, e o middleware tenta cada chave em ordem (`agno/os/middleware/jwt.py`).
- O `MultiFernet` do `cryptography` decifra com qualquer chave da lista, cifra com a primeira e tem `rotate()`, que recifra um token com a primeira chave.
- `jose.jwtVerify` no painel aceita uma chave por chamada.
- O `integration_token` não guarda com qual chave o token foi assinado.

## Decisão

**Uma chave anterior, aceita só na verificação.** Duas variáveis opcionais:

- `JWT_PREVIOUS_PUBLIC_KEY`: a API, o `/mcp` e o proxy do painel aceitam tokens assinados com ela. A emissão usa sempre a chave atual.
- `MCP_SECRETS_PREVIOUS_KEY`: a leitura dos segredos tenta a atual e depois a anterior. A gravação usa sempre a atual.

Uma anterior basta. Rotação é um evento raro, e a janela termina quando o último token antigo vence ou é reemitido. Uma lista abriria espaço para chave velha esquecida aceita para sempre.

**O token diz com qual chave foi assinado.** O cabeçalho do JWT ganha `kid`: os primeiros 16 caracteres do SHA-256 da chave pública em DER. A verificação tenta primeiro a chave do `kid` e depois as outras. O token antigo, sem `kid`, continua valendo pela tentativa em ordem. O `integration_token` ganha a coluna `signing_kid`, preenchida na emissão.

**Comando para recifrar os segredos.** `python -m app.rotate_secrets` passa pelas quatro tabelas, recifra com a chave atual o que estiver na anterior e informa quantos registros mudaram em cada uma. Ele roda numa transação só e pode rodar de novo sem efeito. Valor que nenhuma das duas chaves decifra interrompe o comando antes de gravar qualquer coisa, com a tabela e o id.

**Estado da rotação para o owner.** `GET /api/v1/key-rotation` mostra:

- o `kid` atual e o anterior;
- quantos tokens de integração ativos ainda estão na chave anterior ou sem `kid`;
- se a chave anterior dos segredos está configurada e quantos segredos ainda dependem dela, por tabela.

O painel mostra isso numa seção para o owner. A rotação acaba quando os dois contadores chegam a zero, e aí as variáveis `*_PREVIOUS_*` podem sair.

**Passo a passo na documentação.** `docs/rotacao-de-chaves.md` descreve a ordem para cada chave. Ele substitui a ação manual da Fase 11 no roadmap.

## Alternativas descartadas

- **Endpoint JWKS com várias chaves.** Faz sentido quando outros serviços verificam os tokens. Aqui só a própria instância verifica, e a chave pública já chega por variável de ambiente à API e ao painel.
- **Cofre externo (Vault, KMS).** Resolve rotação automática, mas cria uma dependência de infraestrutura que a instância não tem e que a demo não teria. A variável anterior cobre a troca manual, que é o caso real.
- **Trocar a chave e pedir login de novo.** Serve para sessões de 1 hora. Derruba os tokens de integração em uso por até 90 dias, sem aviso para quem integrou.
- **Recifrar só ao ler (preguiçoso).** Nunca termina para segredo que ninguém lê, e a chave anterior teria que ficar para sempre.

## Consequências

- Rotacionar o JWT não derruba ninguém. Sessões do painel migram sozinhas em 1 hora. Integrações migram quando o token é reemitido, e o painel mostra quantas faltam.
- Rotacionar os segredos é: configurar a nova como atual e a velha como anterior, reiniciar, rodar o comando e tirar a anterior.
- Enquanto a chave anterior do JWT estiver configurada, um token roubado assinado com ela continua valendo até vencer. A revogação por `jti` segue funcionando nesse período, e o estado da rotação mostra o que ainda depende da chave velha.
- **Chave privada vazada não usa a anterior.** Quem tem a privada velha assina tokens novos que a pública anterior aceitaria, inclusive com `jti` que nunca foi revogado. Nesse caso a troca corta todas as sessões e todos os tokens de integração, como hoje. A chave anterior serve para troca de rotina. O passo a passo diz isso antes do primeiro comando.
- O painel precisa das duas chaves públicas no proxy, como a API.
- Uma migration: `signing_kid` no `integration_token`.

## O que me faria reverter

Se outro serviço passar a verificar os tokens da instância, a chave anterior por variável deixa de bastar e um JWKS publicado vira o caminho. Se a instância passar a rodar num provedor com KMS gerenciado, a cifra dos segredos migra para ele e o comando de recifrar sai.
