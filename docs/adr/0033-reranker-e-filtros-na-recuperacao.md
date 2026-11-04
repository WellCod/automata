# ADR-0033 — Reranker por cross-encoder e filtros escolhidos pelo modelo na recuperação

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-04

## Contexto

O ADR-0017 deu a cada base uma estratégia de recuperação: MMR, recência e HyDE. Ficaram dois buracos:

- **A nota da busca não é relevância.** A busca híbrida ordena por proximidade de embedding e por full-text. Um trecho que repete as palavras da pergunta sem responder fica na frente de um que responde com outras palavras. Um cross-encoder lê a pergunta e o trecho juntos e dá uma nota de relevância de fato. O ADR-0017 descartou esse caminho porque o texto sai da instância, mas quem opera a instância pode querer a troca.
- **O modelo não tem como restringir a busca.** Uma base com manuais de três produtos devolve trechos dos três quando a pergunta é sobre um só. O modelo sabe qual produto o cliente tem, mas a tool só recebe a pergunta.

Verificado no Agno 3.1.8 instalado:

- **`CohereReranker`** (`agno.knowledge.reranker.cohere`): `model` (padrão `rerank-multilingual-v3.0`), `api_key` e `top_n`. Precisa do pacote `cohere`, que não está no projeto.
- **`AwsBedrockReranker`** (`agno.knowledge.reranker.aws_bedrock`): Amazon Rerank 1.0 e Cohere Rerank 3.5 pelo Bedrock, com `aws_region`. Usa o `boto3`, que já está no projeto (ADR-0024), e as credenciais da AWS do ambiente.
- Os dois implementam o mesmo `Reranker.rerank(query, documents, limit)` que o MMR e a recência usam. Em erro, a base volta à busca sem reordenar, como no ADR-0017.
- **`PgVector.search(query, limit, filters)`** filtra pelo `meta_data` dos trechos (`meta_data @> filtro`).
- Hoje o `meta_data` de cada trecho leva só `content_id` e `source` (`app/knowledge/ingest.py`). O documento não tem campos próprios.
- **`enable_agentic_knowledge_filters`** do `Agent` só vale para o `knowledge=` do Agno. A busca do Automata é uma tool por base (ADR-0012), então os filtros escolhidos pelo modelo precisam entrar na própria tool.

## Decisão

**Cross-encoder por base.** O `retrieval` da base ganha `cross_encoder`, vazio por padrão, com:

- `provider`: `cohere` ou `bedrock`;
- `model`: para o Cohere, `rerank-v3.5` (padrão) ou `rerank-multilingual-v3.0`; para o Bedrock, `cohere.rerank-v3-5:0` (padrão) ou `amazon.rerank-v1:0`.

Ele roda antes da estratégia (MMR ou recência), sobre o mesmo lote de candidatos do `search_limit`, contra a pergunta original. A busca fica assim:

1. HyDE, se ligado;
2. lote de candidatos;
3. cross-encoder ordena por relevância;
4. MMR ou recência reordenam o resultado;
5. corte em K.

O provedor só aparece no painel quando está configurado: `COHERE_API_KEY`, ou `AWS_REGION` com credenciais da AWS. Salvar uma base com provedor sem configuração dá erro na escrita, como a moderação (ADR-0013).

O custo é por busca, não por token:

- Cohere: US$ 2 por mil buscas;
- Amazon Rerank: US$ 1 por mil;
- Cohere pelo Bedrock: US$ 2 por mil.

Ele entra no consumo pelo `record_side_usage` (ADR-0030), na conta do agente que buscou, e a busca de teste mostra o valor.

**Metadados por documento.** O `knowledge_content` ganha `fields` (JSONB, migration 0043; `metadata` é nome reservado no SQLAlchemy): até 10 campos. Cada campo tem:

- nome de 1 a 40 caracteres, só minúsculas, dígitos e `_`;
- valor em texto de até 100 caracteres.

Os campos entram no `meta_data` de cada trecho, dentro de `fields`, na ingestão, na sincronização de conector e no reprocessamento. Editar os campos de um documento atualiza os trechos por SQL (`meta_data = jsonb_set(...)`), sem embedar de novo.

**Filtros escolhidos pelo modelo.** O `retrieval` ganha `agentic_filters`, desligado por padrão. Ligado, a tool `buscar_<base>` ganha um argumento opcional `filtros`, um objeto de campo para valor. A descrição da tool lista os campos e até 20 valores de cada um, lidos dos documentos da base com cache curto. O modelo vê, por exemplo, `produto: "plano a", "plano b"` e passa `{"produto": "plano a"}`. A busca aplica o filtro no `PgVector.search`. Algumas regras:

- Campo ou valor que não existe na base é ignorado, e a tool avisa no resultado.
- Busca com filtro sem nenhum trecho cai na busca sem filtro e avisa. Um filtro errado do modelo não pode virar "não há nada sobre isso".

A busca de teste aceita os mesmos filtros.

## Alternativas descartadas

- **Reranker local (SentenceTransformer, Infinity).** O modelo pesa centenas de MB na imagem e roda em CPU, com latência alta. Fica possível depois, como provedor a mais.
- **Filtros fixos por agente** (`knowledge_filters`). Servem quando um agente atende um produto só, mas não quando o produto depende da conversa. O agente pode ter uma base própria nesse caso.
- **Usar o `knowledge=` do Agno para ter os filtros prontos.** O Agno aceita uma base por agente, e o ADR-0012 escolheu uma tool por base.

## Consequências

- Com cross-encoder ligado, o texto dos candidatos sai da instância para o provedor a cada busca. O painel avisa ao ligar.
- A busca ganha uma chamada de rede de 100 a 300 ms.
- Documento enviado antes da fase não tem campos. Ele entra no filtro depois que alguém edita os campos dele.
- O modelo pode errar o filtro. O retorno sem filtro, com aviso, troca precisão por não perder a resposta.

## Plano das fases seguintes

O backlog dos ADRs até o 0032 foi pedido inteiro em 2026-11-04. A ordem fica no roadmap: Fases 36 a 42, cada uma com o próprio ADR.
