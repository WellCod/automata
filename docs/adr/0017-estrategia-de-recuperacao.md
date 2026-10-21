# ADR-0017 — Estratégia de recuperação por base: reranker do Agno e HyDE com modelo nosso e medido

**Status:** Aceito
**Data:** 2026-10-21

## Contexto

A busca das bases de conhecimento (ADR-0012) é híbrida, com vetor e full-text em português, e devolve os K trechos mais próximos da pergunta. Três problemas aparecem com conteúdo real:

- **Trechos quase iguais ocupam o top-K.** Um documento longo partido em pedaços, ou duas versões do mesmo texto, trazem K trechos que dizem a mesma coisa. Com isso, o segundo documento relevante fica de fora.
- **A pergunta não se parece com a resposta.** "Posso devolver depois de usar?" e "Produtos utilizados não são aceitos para devolução" ficam longe no espaço do embedding, embora um responda o outro.
- **Documento substituído ranqueia igual ao novo.** A busca não tem noção de tempo, e a política de 2025 compete de igual para igual com a de 2026.

A Fase 13 deixou o reranker para depois, e a v3 do Agno trouxe as peças prontas.

Verificado no Agno 3.1.8 instalado e no código atual:

- **`Reranker`** (`agno.knowledge.reranker.base`): `rerank(query, documents, limit)` e `search_limit(max_results)`. Esse método pede ao banco vetorial um lote maior de candidatos (`candidate_multiplier`, até `max_candidates`), porque só dá para resgatar um trecho que foi buscado.
- **`MMRReranker`**: escolhe trechos relevantes e diferentes entre si, com `lambda_mult` de 0 (só diversidade) a 1 (só relevância). Precisa do embedding de cada candidato, e o PgVector devolve esse embedding na busca. A consulta é embedada com o mesmo embedder da base.
- **`RecencyReranker`**: mistura a nota da busca com um decaimento exponencial pela idade, com meia-vida e peso. A data vem do `meta_data` ou da coluna da tabela com `PgVector(return_updated_at=True)`. Trecho sem data fica só com a relevância.
- **`HyDE`** (`agno.knowledge.query_transformer.hyde`): pede a um modelo uma resposta hipotética e busca com ela no lugar da pergunta. São uma chamada de modelo por busca e, se a chamada falha, ele busca com a pergunta original. **Sem `model`, cai no `OpenAIResponses` padrão**, a mesma armadilha do juiz da Fase 16.
- **Rerankers por cross-encoder** (Cohere, Infinity, SentenceTransformer, Bedrock): exigem outro provedor, com o texto saindo da instância, ou um modelo local pesado na imagem.
- A busca do Automata chama o `PgVector.search` direto, com uma tool por base (ADR-0012), e não o `Knowledge.search`, onde fica o pipeline do Agno. As peças acima funcionam fora do `Knowledge`.
- Os evals de recuperação (`test_evals_retrieval.py`) medem se o documento esperado volta entre os 3 primeiros trechos: os literais em todo PR, com o embedder local, e os semânticos à noite, com a Voyage.

## Decisão

**Estratégia de recuperação por base, fora de versão como a própria base.** O `knowledge_base` ganha `retrieval` (JSONB, migration 0028), com:

- `reranker`: `none` (padrão), `mmr` ou `recency`;
- `mmr_lambda`, padrão 0,5;
- `recency_half_life_days`, padrão 30, e `recency_weight`, padrão 0,3;
- `hyde`, desligado por padrão, e `hyde_model`, escolhido entre os modelos da matriz.

A estratégia é da base porque depende do conteúdo dela: uma base de políticas versionadas pede recência, e uma de manuais repetitivos pede diversidade. Todos os agentes que usam a base recebem a mesma busca.

**O pipeline fica dentro do `search_base`, com as peças do Agno.** Na ordem:

1. Com HyDE ligado, a consulta vira a resposta hipotética.
2. Com reranker, a busca pede `search_limit(K)` candidatos.
3. O reranker ordena contra a **pergunta original**, e o resultado é cortado em K.

Sem estratégia, a busca é a mesma de hoje. Falha no reranker devolve a busca sem reordenar e registra um aviso: busca pior é melhor que nenhuma busca.

**HyDE com modelo nosso e medido.** O modelo sai sempre do `hyde_model` da base e é passado explicitamente, para nunca cair no padrão do Agno. O medidor do juiz (`app/evals/judge.py`) passa a embrulhar também o `invoke` síncrono, que é o caminho do `HyDE.transform`.

- Na busca feita por um agente, os tokens viram um `usage_event` daquele agente, com o `run_id` e o `user_id` do `RunContext` que o Agno injeta na tool. Na suíte de testes, entra também o `eval_run_id`.
- Na busca de teste do painel, os tokens aparecem na resposta e não são atribuídos a nenhum agente.
- No modo demo, o HyDE não roda: as respostas gravadas não inventam um trecho plausível, e a busca segue com a pergunta.

**A busca de teste compara.** `POST /knowledge-bases/{id}/search` ganha `compare: true`, que devolve lado a lado os trechos com a estratégia da base e sem ela. Assim quem configura vê o efeito antes de os agentes usarem.

**Evals por estratégia.** O eval literal roda com cada reranker, e o recall não pode cair: estratégia que piora o óbvio não entra. O eval noturno com a Voyage mede o recall semântico de cada estratégia e registra os números no log. Ele falha se alguma ficar abaixo da busca simples além de uma pergunta de tolerância. O HyDE roda à noite só com chave de modelo configurada.

## Alternativas descartadas

- **Reranker por cross-encoder (Cohere, Bedrock, SentenceTransformer).** É o que mais melhora a ordem, mas a Cohere e a Bedrock levam os trechos para mais um provedor, e o SentenceTransformer põe o PyTorch na imagem da API. Fica como opção quando um cliente já usar um desses provedores. A interface `Reranker` deixa a troca barata.
- **Trocar a busca direta pelo `Knowledge.search` do Agno.** O pipeline viria pronto, mas o `Knowledge` aceita uma base por agente, e o ADR-0012 escolheu uma tool por base. Também teríamos de refazer a medição dos embeddings e o tratamento de erro do embedder, que hoje são nossos. As mesmas peças, usadas na nossa busca, dão o mesmo resultado.
- **Estratégia por agente, no vínculo com a base.** A mesma base buscaria de um jeito para um agente e de outro para outro, e o resultado da busca de teste deixaria de valer para todos. A estratégia depende do conteúdo. O vínculo continua só com `max_results`.
- **HyDE sempre ligado.** Uma chamada de modelo a mais em cada busca soma latência e custo a toda conversa que consulta a base, e o ganho depende do conteúdo. Fica opt-in, com a comparação na busca de teste para decidir.

## Consequências

- MMR pode tirar do top-K um trecho relevante que repete outro. É o objetivo, mas um caso de teste que esperava os dois trechos muda de resultado.
- Recência depende da data dos trechos. Conteúdo reindexado ganha data nova, mesmo sem mudança de texto, porque a reingestão substitui os trechos.
- HyDE soma uma chamada de modelo por busca. O custo aparece no consumo do agente, e a busca de teste mostra os tokens antes de ligar.
- Mudar a estratégia muda o comportamento de todos os agentes que usam a base, sem nova versão de agente. A suíte de testes agendada (ADR-0016) pega a regressão, e a comparação da busca de teste mostra o efeito antes.
- Uma migration: `retrieval` no `knowledge_base`.

## O que me faria reverter

- Os evals noturnos mostrarem, nas bases de exemplo e nas de clientes, que nenhuma estratégia melhora o recall. Nesse caso, a opção sai do painel para não virar configuração sem efeito.
- Um cliente com Cohere ou Bedrock já contratados. Nesse caso, o reranker por cross-encoder entra como mais uma opção de `reranker`, com o texto indo para um provedor que ele já usa.
