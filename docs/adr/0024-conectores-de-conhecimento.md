# ADR-0024 — Conectores de conhecimento (GitHub, S3, SharePoint) e reindexação agendada

**Status:** Aceito
**Data:** 2026-10-21

## Contexto

Uma base de conhecimento (ADR-0012) recebe conteúdo de três jeitos: arquivo enviado, URL baixada uma vez e texto colado. Tudo é foto do momento do envio.

Os problemas:

- **A base envelhece em silêncio.** A política de troca muda no site, e a base segue respondendo com a versão do mês passado. Ninguém reenvia a URL.
- **O conteúdo de verdade mora em outro lugar.** A documentação fica num repositório, os contratos num bucket, os procedimentos numa pasta do SharePoint. Copiar arquivo por arquivo para o painel não escala e desatualiza no dia seguinte.

Verificado no Agno 3.1.8 instalado (`agno.knowledge.remote_content`):

- Há `S3Config`, `GitHubConfig` e `SharePointConfig`, com credenciais e caminho. O `S3Config` também lista arquivos.
- O download e a leitura desses conteúdos acontecem dentro do `Knowledge.add_content` do Agno. A nossa ingestão não passa por ele: ela lê com o `ReaderFactory`, mede o embedder, grava `content_id` em cada trecho e cobra o consumo por base (ADR-0012).
- Os pacotes de que esses loaders dependem (`boto3`, `msal`) não estão instalados.

No código atual:

- `app/knowledge/ingest.py` ingere bytes num `knowledge_content` já criado.
- `app/knowledge/fetch.py` baixa URL com o filtro de saída do MCP, seguindo redirect à mão.
- O segredo de servidor MCP e de webhook é cifrado com `MCP_SECRETS_KEY` (Fernet) e nunca volta na API.
- O poller da API roda a cada minuto (suítes agendadas e avisos) e reivindica trabalho com `FOR UPDATE SKIP LOCKED`.

## Decisão

**Conector por base, com o download nosso e a ingestão de sempre.** Uma base pode ter conectores, cada um com:

- `kind`: `github`, `s3` ou `sharepoint`;
- configuração sem segredo:
  - GitHub: repositório, branch e pasta;
  - S3: bucket, região, prefixo e endpoint opcional, para MinIO e compatíveis;
  - SharePoint: host, site, pasta, tenant e client id;
- segredo cifrado com `MCP_SECRETS_KEY`: token do GitHub, chave de acesso do S3 ou client secret do SharePoint. O segredo é mostrado como "configurado" e nunca devolvido.

O download é feito por nós:

- GitHub pela API REST (árvore do branch e conteúdo bruto);
- SharePoint pelo Microsoft Graph com client credentials, pelo `httpx`, sem pacote novo;
- S3 com `boto3`, a única dependência nova.

Os bytes passam pelo mesmo `ingest`. Cada arquivo vira um `knowledge_content` ligado ao conector, com o caminho remoto e a versão remota (sha do Git, ETag do S3, eTag do Graph).

**Sincronizar compara pela versão remota.**

- Arquivo novo é ingerido.
- Versão mudada é reindexada: os trechos antigos saem antes.
- Arquivo que sumiu da origem sai da base, com os trechos.
- Versão igual não baixa de novo.

Só entram as extensões que a ingestão lê, até 500 arquivos e o tamanho máximo de arquivo da base. O que passa do limite fica no resumo da sincronização.

**Reindexação agendada.**

- O conector ganha `sync_every_hours`, de 1 a 168, ou vazio para só manual.
- Conteúdo de URL ganha `refresh_every_hours`. Na reindexação a URL é baixada de novo, e só volta a indexar se o hash do conteúdo mudou.
- O poller da API reivindica o que venceu com `SKIP LOCKED` e marca o próximo horário antes de trabalhar, como as suítes agendadas.

**Saída filtrada e papéis.**

- Endpoint de S3 próprio e URL de GitHub Enterprise passam pelo `check_url`, no cadastro e a cada sincronização.
- GitHub, AWS e Graph usam hosts fixos.
- Cadastrar ou trocar a credencial de conector é do owner, como servidor MCP, porque define com qual credencial a API sai. O editor da base sincroniza e vê o resumo.

## Alternativas descartadas

- **Usar o `Knowledge.add_content(remote_content=...)` do Agno.** Ele lê e grava pelo `Knowledge` dele. Perderíamos o `content_id` por trecho, a medição do embedder e o estado por conteúdo que o painel mostra, ou teríamos duas ingestões.
- **Webhook da origem (push do GitHub, evento do S3) no lugar de agendamento.** É mais imediato, mas exige expor uma rota pública por origem e configurar cada uma do outro lado. O agendamento cobre o caso comum, e o botão Sincronizar cobre a urgência.
- **`msal` para o SharePoint.** O client credentials é uma chamada HTTP só, e o `httpx` já está na stack.
- **Reindexar URL sempre, sem comparar hash.** Pagaria embedding de novo para página que não mudou.

## Consequências

- A base acompanha a origem sem ninguém reenviar arquivo.
- Cada sincronização custa embedding só do que mudou. O consumo entra como `ingest` na base, como hoje.
- Um token com acesso amplo dá à base tudo que ele lê dentro do caminho configurado. O painel avisa para usar token de leitura restrito ao repositório ou à pasta.
- Uma dependência nova (`boto3`) na imagem da API.
- Migrations novas: `knowledge_connector` e as colunas de origem e reindexação em `knowledge_content`.

## O que me faria reverter

- O Agno passar a expor o download dos conteúdos remotos separado da gravação. Nesse caso, os downloaders próprios saem e ficam os dele.
- Pedido de sincronização quase em tempo real. Nesse caso, entra o webhook da origem por conector.
