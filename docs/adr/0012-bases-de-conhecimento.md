# ADR-0012 — Bases de conhecimento como cadastro próprio, conteúdo no Agno com pgvector e embeddings da Voyage

**Status:** Aceito
**Data:** 2026-10-16

## Contexto

Os agentes só sabem o que está nas instruções e no que as tools MCP devolvem. Para responder sobre documentos do cliente (manuais, políticas, contratos, base de suporte), o caminho é RAG: indexar o conteúdo em trechos com embeddings e deixar o agente buscar os relevantes antes de responder.

Verificado no Agno 2.8.7 instalado:

- `Knowledge(name, description, vector_db, contents_db, max_results, readers, isolate_vector_search)` com `insert/ainsert(path|url|text_content, metadata, reader, upsert, skip_if_exists)`, `search(query, max_results, filters)`, `get_content_status(id)` (`PROCESSING`, `COMPLETED`, `FAILED`) e `remove_content_by_id`. Os metadados do conteúdo vão para `ai.agno_knowledge` (o `contents_db` é o `PostgresDb` que já usamos).
- `PgVector(table_name, schema="ai", db_url, embedder, search_type=vector|keyword|hybrid, vector_index=HNSW(), reranker)` exige o pacote `pgvector` e a extensão `vector` no Postgres. A imagem `postgres:17` dos compose não tem a extensão.
- `Agent` e `Team` aceitam `knowledge=`, `search_knowledge=True` (tool `search_knowledge_base(query)`, que preenche `run_response.references`) e `knowledge_filters`.
- Readers por extensão: PDF (`pypdf`), DOCX (`python-docx`), Markdown, texto, CSV, JSON e website (`beautifulsoup4`). Chunking padrão de tamanho fixo; há recursivo, por Markdown e semântico.
- As rotas `/knowledge/*` do AgentOS só enxergam instâncias de `Knowledge` conhecidas no boot, descobertas em agentes e times estáticos. As propriedades que fazem a descoberta ignoram `AgentFactory` e `TeamFactory`, que é tudo o que registramos (ADR-0002). Bases criadas pelo painel em tempo de execução não apareceriam.
- A Anthropic não oferece API de embedding e indica a Voyage. O Agno tem `VoyageAIEmbedder` e `OpenAIEmbedder`; não tem embedder da Anthropic.

## Decisão

Base de conhecimento é uma entidade própria (`knowledge_base`), **não versionada**, referenciada pelos configs de agente e time. O conteúdo e os vetores ficam no Agno (`Knowledge` + `PgVector` em uma tabela por base no schema `ai`), acessados só por rotas próprias em `/api/v1/knowledge-bases`. Embeddings da Voyage (`voyage-3.5`, 1024 dimensões) por padrão, OpenAI como alternativa, escolhidos na criação da base e imutáveis depois.

O payload do config ganha `knowledge: [{base_id, max_results}]`. A factory monta o `Knowledge` de cada base ligada e passa ao `Agent` com `search_knowledge=True`; com mais de uma base, uma tool de busca por base, com o nome da base no nome da tool.

## Alternativas descartadas

**Usar as rotas `/knowledge` do AgentOS.** Não enxergam bases criadas depois do boot nem as ligadas a factories, e passar `AgentOS(knowledge=[...])` congela a lista até o próximo restart, o mesmo problema que o #67 resolveu para agentes publicados. Também exigiriam scopes `knowledge:*` do RBAC do Agno, à parte dos nossos.

**Base embutida no payload versionado do agente.** Documento muda por motivo operacional (política revisada, manual novo). Versionar o conteúdo junto obrigaria a republicar o agente a cada upload e duplicaria vetores por versão. Versionar a **ligação** (quais bases o agente usa) basta para publicar e reverter comportamento.

**Uma tabela de vetores para todas as bases, separadas por metadado.** Funciona com `isolate_vector_search`, mas bases com embedders diferentes têm dimensões diferentes e não cabem na mesma coluna `vector(n)`. Tabela por base também deixa remover uma base inteira com um `DROP`.

**Vector DB dedicado (Qdrant, Pinecone, Weaviate).** Mais um serviço em cada instância (ADR-0003). O Postgres já está lá; pgvector com HNSW atende o volume de uma instância single-tenant.

**Embeddings locais (fastembed, sentence-transformers) como padrão.** Sem custo por token, mas pesam a imagem da API (modelo e runtime de inferência), ficam abaixo da Voyage em recuperação e disputam CPU com a API (limite de 0,5 CPU no compose). Ficam para o modo de demonstração.

**Ingestão síncrona no request de upload.** PDF grande leva dezenas de segundos para ler, quebrar e gerar embeddings. O request estouraria o timeout do proxy e o painel ficaria travado.

## Consequências

- Tabela `knowledge_base`: nome, slug, descrição, embedder e dimensões, tamanho de trecho, nome da tabela de vetores e auditoria. Trocar o embedder de uma base é recriá-la e reindexar.
- Postgres passa para `pgvector/pgvector:pg17` em todos os compose e nos testes; migration roda `CREATE EXTENSION IF NOT EXISTS vector`. Dependências novas: `pgvector`, `voyageai`, `pypdf`, `python-docx`, `beautifulsoup4`.
- `VOYAGE_API_KEY` (ou `OPENAI_API_KEY`) passa a ser obrigatória para criar base com o embedder correspondente. A Voyage cobra por token depois de uma faixa gratuita; o custo de embedding entra no metering.
- Ingestão assíncrona: o upload responde 202 e processa em background na própria API; o painel consulta o status. Restart no meio deixa o conteúdo em `PROCESSING`; no boot, o que estiver parado há mais de N minutos vira `FAILED` com motivo, e o usuário reenvia. Limites de tamanho e de tipos por settings.
- Ingestão por URL usa a mesma checagem de SSRF dos servidores MCP (ADR-0010), na hora de salvar e na hora de buscar.
- Conteúdo de documento é dado, não instrução. As instruções de agente com base ligada ganham um bloco fixo dizendo isso, e o linter avisa quando falta guardrail sobre uso das fontes. Não elimina prompt injection por documento; reduz.
- Editar ou remover documento afeta na hora todo agente que usa a base, como servidores MCP. O painel mostra quem usa a base antes de remover.
- Papéis: editor cria base e sobe ou remove conteúdo; viewer lista e faz busca de teste. Tokens de integração não acessam bases diretamente, só através dos agentes liberados.
- Modo `DEMO_REPLAY` usa um embedder determinístico local, sem chave, para a demo continuar offline (ADR-0008).

## O que me faria reverter

- Volume de upload competir com os runs pela CPU da API: mover a ingestão para um worker separado com fila (o Redis já está no compose).
- Base passar de alguns milhões de trechos com latência de busca acima de 300 ms medidos: vector DB dedicado.
- Cliente sem permissão para mandar conteúdo a terceiros: embedder local por instância, escolhido por variável de ambiente.
- Necessidade de saber qual conteúdo estava na base quando uma resposta foi dada (auditoria regulatória): versionar conteúdo e registrar a versão no run.
