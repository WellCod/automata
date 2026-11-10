# ADR-0042 — Login por SSO via OIDC

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-10

## Contexto

O painel só tem login por e-mail e senha (ADR-0005). Numa empresa isso significa mais uma senha para cada pessoa e um owner criando e desativando conta à mão quando alguém entra ou sai do time. O que se espera é entrar pelo provedor de identidade que a empresa já usa (Entra ID, Google Workspace, Okta, Keycloak, Clerk) e o acesso acompanhar o cadastro de lá.

O que existe e serve:

- A API emite o JWT da sessão (`issue_token`) e o painel guarda no cookie pelo BFF. O resto do sistema (scopes, corte de sessão por `tokens_valid_after`, revogação por `jti`, trilha de auditoria) não depende de como a pessoa provou quem é.
- `guarded_client` (ADR-0010) conecta só em endereço público conferido, sem seguir redirect.
- O `proxy.ts` do painel já deixa `/api/auth/*` sem cookie.

## Decisão

**OIDC genérico, um provedor por instância**, configurado no ambiente: `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI` (a rota `/api/auth/oidc/callback` do painel) e `OIDC_LABEL` (o texto do botão). Qualquer provedor que publique `/.well-known/openid-configuration` serve, inclusive o Clerk como provedor OAuth. Sem SDK de fornecedor: o fluxo é o authorization code com PKCE, feito pela API com `httpx` e `PyJWT`.

**Fluxo.**

1. O painel chama `POST /api/v1/auth/oidc/start` e redireciona o navegador para a URL devolvida.
2. A API gera `state`, `nonce` e o verificador do PKCE, guarda numa linha de `oidc_login` (migration 0056) com validade de 10 minutos e monta a URL a partir do discovery.
3. O provedor devolve o navegador para o callback do painel com `code` e `state`. O painel repassa para `POST /api/v1/auth/oidc/callback`.
4. A API consome a linha do `state` (uso único), troca o `code` no `token_endpoint` com o segredo e o verificador e confere o `id_token`: assinatura pela chave do `jwks_uri` (RS256 ou ES256, nunca `none` nem HS*), `iss`, `aud`, `exp` e `nonce`.
5. A API emite o JWT de sempre, e o painel grava o cookie como no login por senha.

Discovery, token e JWKS saem pelo `guarded_client`; discovery e JWKS ficam em cache por uma hora, e uma chave nova no `kid` força uma busca.

**Quem entra e com que papel.**

- A conta é achada pelo par `(sso_issuer, sso_subject)`. Na primeira vez, por e-mail, só com `email_verified` verdadeiro, e a conta passa a guardar o par. Sem conta, é criada sem senha.
- O papel vem de `OIDC_ROLE_CLAIM` (caminho com ponto, como `groups` ou `public_metadata.role`) mapeado por `OIDC_ROLE_MAP` (`grupo=papel` separados por vírgula). Valor fora do mapa usa `OIDC_DEFAULT_ROLE`; sem padrão, o login é recusado.
- O papel é sincronizado a cada login, com as regras de sempre: mudar de papel corta as sessões antigas, e o último owner ativo não é rebaixado (o login entra com o papel atual e a recusa vai para o log).
- `OIDC_ALLOWED_DOMAINS` limita os domínios de e-mail aceitos.
- Conta desativada no painel não entra, nem pelo SSO.

**Senha.** O login por senha continua, para o owner de emergência e para quem não usa SSO. `PASSWORD_LOGIN=false` desliga para quem não é owner. Conta criada pelo SSO não tem senha e o login por senha dela falha como credencial inválida.

## Alternativas descartadas

- **SDK do Clerk (ou de outro fornecedor) no painel.** Prende o painel a um fornecedor e passa a sessão para o cookie dele, fora do JWT da API que o resto do sistema confere. O Clerk entra pelo mesmo OIDC.
- **SAML.** Mais pesado e sem ganho para os provedores atuais, que falam OIDC. Fica como gatilho se um cliente só tiver SAML.
- **Fluxo no painel.** O segredo do cliente e a validação do token ficariam no Node; a API já guarda segredos e emite a sessão.
- **Provisionamento por SCIM.** A sincronização no login cobre entrada e mudança de papel. A saída depende do provedor recusar o login; a sessão aberta dura no máximo 1 hora, ou o owner desativa no painel. Gatilho de revisão se isso não bastar.

## Consequências

- A instância passa a confiar no provedor para dizer quem é a pessoa e o grupo dela: um grupo mapeado para `owner` dá acesso total.
- Pessoa que sai da empresa perde o acesso no próximo login, não na hora.
- O login por SSO fica no log estruturado, como o por senha; a trilha de auditoria segue fora de `/api/v1/auth/*` (ADR-0041).
