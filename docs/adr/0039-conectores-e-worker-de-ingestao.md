# ADR-0039 — Google Drive e Cloud Storage, filtro por nome, webhook da origem e worker de ingestão

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-04

## Contexto

O ADR-0024 trouxe os conectores de GitHub, S3 e SharePoint e deixou para depois: Google Drive e GCS, filtro por padrão de nome de arquivo e o webhook da origem. O ADR-0012 deixou para depois o worker de ingestão separado. Os problemas:

- **Empresas no Google Workspace não têm conector.** A política de atendimento mora num Google Docs, e alguém precisa exportar e subir à mão.
- **O conector traz tudo da pasta.** Um repositório com `docs/` e `CHANGELOG.md` indexa os dois. Não há como pegar só `*.md` de `politicas/` ou ignorar `rascunhos/`.
- **A sincronização é por relógio** (de hora em hora, no mínimo). O texto corrigido no GitHub fica errado no agente até a próxima rodada.
- **A ingestão roda no processo da API**, em `BackgroundTasks`. Um PDF grande ou uma sincronização de cem arquivos ocupa a CPU que atende os runs, e uma reinicialização no meio deixa o conteúdo em processamento (resolvido hoje pelo `_fail_stale_ingestions` no boot).

Verificado:

- A Drive API v3 tem as rotas `GET /drive/v3/files` (`q="'<pasta>' in parents and trashed=false"`, `fields`, `pageToken`), `GET /files/{id}?alt=media` (binário) e `GET /files/{id}/export?mimeType=text/plain` (Google Docs). A planilha sai em `text/csv`. Os drives compartilhados precisam de `supportsAllDrives` e `includeItemsFromAllDrives`.
- A JSON API do Cloud Storage tem as rotas `GET /storage/v1/b/{bucket}/o` (`prefix`, `pageToken`) e `GET .../o/{objeto}?alt=media`. O objeto traz `generation` e `md5Hash`.
- A conta de serviço do Google se autentica por JWT RS256 assinado com a chave privada do JSON, trocado em `oauth2.googleapis.com/token` (`grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`). O PyJWT e o `cryptography` já estão no projeto, então não precisa da biblioteca do Google.
- O GitHub assina o webhook com `X-Hub-Signature-256: sha256=<HMAC-SHA256 do corpo>`.
- O app externo (`app/main.py`) já tem rota pública fora do JWT, o login. É ali que entra o webhook.

## Decisão

**Google Drive e Cloud Storage.** Dois tipos novos de conector:

- **`gdrive`:** `folder_id` e `shared_drive` (bool). Os subdiretórios são visitados até 5 níveis. O Google Docs vira `.txt`, a planilha `.csv` e a apresentação `.txt`. O resto baixa direto quando a extensão é das que a ingestão lê. A versão é o `md5Checksum` ou, nos arquivos nativos do Google, o `modifiedTime`.
- **`gcs`:** `bucket` e `prefix`. A versão é o `generation`.

O segredo dos dois é o JSON da conta de serviço, cifrado como os outros segredos (ADR-0010). Só leitura: `drive.readonly` e `devstorage.read_only`. As chamadas passam pelo cliente com filtro de saída, como as dos outros conectores.

**Filtro por nome.** A configuração de todo conector ganha `include` e `exclude`: até 10 padrões cada, no estilo `politicas/**/*.md`, comparados com o caminho relativo à pasta. Sem `include`, entra tudo. `exclude` vence `include`. O teste de conexão mostra a amostra já filtrada, e um arquivo que sai do filtro sai da base na próxima sincronização, como um arquivo apagado na origem.

**Webhook da origem.** O conector pode ganhar um segredo de webhook, gerado pela API e mostrado uma vez. `POST /api/v1/knowledge-connectors/{id}/webhook` é público, fora do JWT, e exige:

- `X-Hub-Signature-256`, no formato do GitHub, ou `X-Automata-Signature`, com o HMAC-SHA256 do corpo;
- comparação em tempo constante;
- corpo de até 1 MB e uma chamada por minuto por conector.

A chamada válida agenda uma sincronização. O conteúdo do evento não é lido: a sincronização lista a origem de novo. Um conector sem segredo de webhook responde 404.

**Worker de ingestão.** Com `INGEST_WORKER=true`, a API não processa mais. Ela grava um job em `ingest_job` (migration 0049), com tipo, alvo, situação, tentativas e erro, e o processo `python -m app.knowledge.worker` executa. Os tipos são os cinco caminhos de hoje:

- arquivo e texto, lidos do original guardado (ADR-0029);
- URL;
- reindexação de URL;
- sincronização de conector;
- reprocessamento.

O worker reivindica com `FOR UPDATE SKIP LOCKED`, então várias réplicas dividem a fila. O job travado há mais de 30 minutos volta para a fila uma vez e depois falha. O compose ganha o serviço `ingest-worker` no perfil `worker`. Sem a variável, tudo segue em `BackgroundTasks`, como hoje.

## Alternativas descartadas

- **Biblioteca oficial do Google (`google-api-python-client`).** Seriam centenas de MB de dependência para três chamadas REST. A troca do JWT é curta e já tem as peças no projeto.
- **Regex no filtro por nome.** O motivo é o mesmo do ADR-0032: o `re` segura o GIL e um padrão ruim trava. O glob é linear e é o que quem cuida do repositório conhece.
- **Worker pela fila durável do Agno** (ADR-0020). Ela serve a runs de agente e time. A ingestão não é um componente do AgentOS.

## Consequências

- O JSON da conta de serviço dá acesso a tudo que ela vê. A recomendação, escrita no painel, é compartilhar com ela só a pasta da base.
- O webhook é uma rota pública: o segredo é a única defesa. Ele não aparece de novo, e trocar gera outro.
- Com o worker ligado, um conteúdo enviado só é processado quando o worker está no ar. O painel mostra "na fila", e o `/health` da API não sabe do worker.
