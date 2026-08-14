# Demo local — sem credencial de LLM

Este guia mostra como rodar o Automata localmente em modo demo com dados realistas e respostas pré-gravadas, sem necessitar de chave de API de nenhum provedor de IA.

## Como funciona

A variável `DEMO_REPLAY=true` substitui o modelo de LLM por `ReplayModel`, que lê arquivos JSON de `api/fixtures/` e cicla pelas respostas. O painel funciona normalmente — edição, versionamento, modo teste, analytics — mas as respostas do agente são pré-gravadas.

## Subindo o ambiente

```bash
# 1. Clone e configure
git clone https://github.com/WellCod/automata.git
cd automata
bash scripts/bootstrap.sh

# 2. Sobe banco + API em modo demo
DEMO_REPLAY=true \
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 3. Painel
pnpm --filter web dev
```

## Populando com dados de demonstração

```bash
# Cria owner, 5 agentes publicados e 500 runs históricos (90 dias)
docker exec \
  -e SEED_OWNER_EMAIL="admin@automata.dev" \
  -e SEED_OWNER_PASSWORD="Automata2024!" \
  automata-api-1 \
  uv run python scripts/seed.py full
```

Acesse `http://localhost:3000` e faça login com as credenciais acima.

## O que o seed `full` cria

### Agentes

| Agente | Modelo | Uso esperado |
|--------|--------|-------------|
| Analista Financeiro | claude-opus-4-7 | Análises de balanço, valuation, due diligence |
| Redator de Conteúdo | claude-sonnet-4-6 | Posts LinkedIn, e-mail marketing, scripts |
| Atendimento ao Cliente | claude-haiku-4-5 | Dúvidas, reclamações, solicitações |
| Suporte Técnico | claude-haiku-4-5 | Incidentes de software e infraestrutura |
| Assistente de Código | claude-sonnet-4-6 | Revisão, debugging, implementação |

Cada agente tem instruções completas (persona, objetivo, tom, guardrails) e está publicado com versão ativa.

### Histórico de execuções

500 runs distribuídos nos últimos 90 dias com:

- Taxas de erro realistas por tipo de agente (3–8%)
- Latências proporcionais ao modelo (haiku ~1,1s · sonnet ~3,0s · opus ~4,2s)
- Consumo de tokens e custo por run proporcional ao modelo
- 5 usuários fictícios para simular ambiente multi-usuário

Esses dados alimentam o painel **Analytics** com gráficos de volume, latência p50/p95, taxa de erro e custo por agente.

## Fixtures de resposta

As respostas pré-gravadas estão em `api/fixtures/`:

| Arquivo | Usado por |
|---------|-----------|
| `claude-opus-4-7.json` | Analista Financeiro |
| `claude-sonnet-4-6.json` | Redator de Conteúdo, Assistente de Código |
| `claude-haiku-4-5.json` | Atendimento ao Cliente, Suporte Técnico |
| `default.json` | Fallback para qualquer outro modelo |

Para adicionar respostas: edite o arquivo JSON correspondente ao `model_id` do agente. O `ReplayModel` cicla pela lista em ordem.

## Testando o modo teste no painel

1. Abra qualquer agente na lista
2. Clique na aba **Teste**
3. Envie qualquer mensagem
4. A resposta virá do arquivo de fixture — sem latência de rede, sem custo

Para ver uma resposta diferente, envie outra mensagem. O modelo cicla pelas respostas na ordem do JSON.

## Variáveis de ambiente relevantes

| Variável | Valor | Efeito |
|----------|-------|--------|
| `DEMO_REPLAY` | `true` | Substitui todos os modelos por ReplayModel |
| `SEED_OWNER_EMAIL` | qualquer e-mail | Login do owner criado pelo seed |
| `SEED_OWNER_PASSWORD` | senha segura | Senha do owner (mín. 12 chars) |

## Resetando os dados

```bash
# Remove todos os dados e recria o schema
docker compose down -v
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
docker exec \
  -e SEED_OWNER_EMAIL="admin@automata.dev" \
  -e SEED_OWNER_PASSWORD="Automata2024!" \
  automata-api-1 \
  uv run python scripts/seed.py full
```
