# ADR-0029 — Chunking por base e compressão do resultado de tool

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-03

## Contexto

A qualidade da busca depende de como o conteúdo é cortado antes de virar vetor, e o custo de um run com tools depende do tamanho do que as tools devolvem. Os dois pontos estão fixos hoje:

- **Corte fixo.** Toda base usa `RecursiveChunking` com sobreposição de 10% do tamanho do trecho (`app/knowledge/ingest.py`). O que muda por base é só o `chunk_size` (ADR-0012), e só para conteúdo novo. Um manual com seções curtas sai cortado no meio de uma seção, e um FAQ com uma pergunta por parágrafo junta perguntas diferentes no mesmo trecho.
- **Sem como reprocessar.** URL e conector podem ser baixados de novo (ADR-0024). Arquivo e texto enviados não guardam o original: só os trechos ficam, no vetor. Trocar o corte de uma base que tem arquivos não alcança o que já está nela.
- **Resultado de tool inteiro no contexto.** Uma tool MCP que devolve um JSON de 30 mil caracteres repassa tudo ao modelo a cada chamada seguinte do run. O limite de chamadas (ADR-0027) segura o laço, mas não o tamanho.

Verificado no Agno 3.1.8 instalado:

- `agno.knowledge.chunking` traz `RecursiveChunking`, `DocumentChunking` (parágrafos, com corte por frase quando o parágrafo passa do tamanho) e `FixedSizeChunking`, todas com `chunk_size` e `overlap`. A sobreposição precisa ser menor que o trecho.
- `MarkdownChunking` importa o `unstructured`, que não está no projeto e é uma dependência grande (`agno/knowledge/chunking/markdown.py:7`). `SemanticChunking` e `AgenticChunking` chamam embedder ou modelo por trecho na ingestão.
- `Agent` e `Team` aceitam `compression_manager: CompressionManager`. O manager (`agno/compression/manager.py`) tem os seguintes campos:
  - `model`: sem ele, usa o modelo do agente;
  - `compress_tool_results_limit`: comprime quando há esse número de resultados ainda não comprimidos; o padrão é 3;
  - `compress_token_limit`: comprime quando o contexto passa desse número de tokens;
  - `compress_tool_call_instructions`: prompt da compressão.
- A compressão acumula o consumo no `RunMetrics` do run como `ModelType.COMPRESSION_MODEL` (`manager.py:135`). O `pricing.run_cost` já soma todos os grupos de `RunMetrics.details` (ADR-0027).

## Decisão

**Estratégia de corte por base.** A base ganha `chunking`, com estes campos:

- `strategy`:
  - `recursive`: o corte de hoje, que segue como padrão;
  - `headings`: por títulos de markdown, até o nível escolhido;
  - `paragraphs`: `DocumentChunking`;
  - `fixed`.
- `overlap`: de 0 a 30% do `chunk_size`. Ausente, vale o de hoje (10%).
- `heading_level`: de 1 a 3, só em `headings`.

`headings` é um `ChunkingStrategy` próprio, sem o `unstructured`. Ele abre um trecho em cada título até o nível escolhido e leva o título no início do trecho. A seção que passa do `chunk_size` é cortada pela recursiva. Texto sem título vira um trecho só, ou é cortado pela recursiva se passar do tamanho.

**Prévia sem gravar.** `POST /api/v1/knowledge-bases/{id}/chunk-preview` recebe um texto (até 50 mil caracteres) ou um conteúdo da base e a estratégia a testar, e devolve os primeiros 20 trechos com o tamanho de cada um. A prévia não embeda nada, então não tem custo.

**Original guardado e reprocessamento.** Arquivo e texto enviados a partir desta fase guardam o original numa tabela própria (`knowledge_content_original`, `bytea`, um por conteúdo). O limite é o mesmo do upload (`KNOWLEDGE_MAX_UPLOAD_MB`), e o original é apagado com o conteúdo. `POST /api/v1/knowledge-bases/{id}/reprocess` reprocessa em background o que a base consegue reler:

- URL: baixada de novo;
- conector: o arquivo é baixado do conector;
- arquivo e texto com original guardado: lidos da tabela.

Conteúdo antigo sem original é listado na resposta como "reenviar". Reprocessar apaga os trechos antigos do conteúdo e indexa os novos. O embedding é cobrado de novo, como ingestão (ADR-0012). Durante o reprocessamento, o conteúdo fica `processing` e some da busca.

**Compressão do resultado de tool.** A seção `run` do payload (ADR-0027) ganha `compress_tool_results`, com estes campos:

- `after_results`: de 1 a 10, o número de resultados antes de comprimir; padrão 3;
- `token_limit`: opcional, de 2 mil a 200 mil;
- `model_id`: opcional, um modelo do catálogo para comprimir; vazio, usa o do agente.

Ela vira um `CompressionManager` no agente e no líder do time. Membros de time seguem a própria configuração. O custo da compressão sai pelo `RunMetrics.details` e entra no custo do run e no orçamento (ADR-0021) sem código novo no medidor. O prompt da compressão é o do Agno, que manda manter números, valores, datas e identificadores.

## Alternativas descartadas

- **`MarkdownChunking` do Agno.** Traria o `unstructured` e as dependências dele para a imagem da API só para cortar por título.
- **Corte semântico ou por agente.** Ele embeda ou chama modelo para cada trecho na ingestão, com custo difícil de prever numa base com conectores agendados. Fica para quando houver medida de ganho na busca.
- **Reconstruir o original a partir dos trechos.** Com sobreposição, a remontagem não é exata, e o reader de PDF e DOCX já descartou a estrutura.
- **Comprimir só tools escolhidas.** O manager do Agno comprime qualquer resultado de tool. Filtrar por tool pediria reimplementar o laço do modelo.

## Consequências

- Uma base de FAQ ou manual passa a ser cortada pela estrutura do texto, e quem configura vê os trechos antes de reprocessar.
- O banco guarda o original de arquivo e texto: uma base com 200 PDFs de 10 MB ocupa 2 GB a mais. O limite de upload segue valendo por arquivo.
- Trocar a estratégia não reprocessa sozinho: o reprocessamento é um botão, porque cobra embedding de novo.
- A compressão troca tokens do modelo principal por uma chamada a mais, de modelo barato se configurado. O resumo pode perder um detalhe que o modelo precisaria. Por isso ela vem desligada e é medida no custo do run.
