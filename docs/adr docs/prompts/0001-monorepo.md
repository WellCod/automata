# ADR-0001 — Monorepo em vez de repositórios separados

**Status:** Aceito
**Data:** 2026-08-05

## Contexto

O projeto tem duas aplicações em linguagens diferentes: uma API em Python sobre o Agno e um painel web em TypeScript. O objetivo primário do repositório, nesta fase, é servir como case técnico avaliável por terceiros; venda é objetivo secundário e futuro.

A primeira inclinação foi separar em `automata-api` e `automata-web`, pelo argumento de toolchain: Python e Node têm CI, cache e cadência de deploy diferentes.

## Decisão

Repositório único `automata`, com `api/` e `web/` na raiz. Sem ferramenta de monorepo — `uv` e `pnpm` ancorados cada um na sua pasta.

## Alternativas descartadas

**Dois repositórios.** O custo não é organizacional, é de contrato: o painel consome a API, e com repos separados o drift de tipos só aparece em runtime. A mitigação existe — publicar `openapi.json` como artifact e falhar o build do front se houver diff — mas é infraestrutura para resolver um problema que o monorepo simplesmente não tem.

O argumento decisivo foi outro. Como case, três repositórios são três pontos de entrada, e quem avalia gasta poucos minutos e abre **um** link. Sem controle de qual link ele abre, a narrativa técnica pode não aparecer. Um ponto de entrada permite dirigir a leitura.

**Repositório separado só para docs.** Padrão de organização com muitos repos. Num projeto de uma pessoa lê como cerimônia — estrutura de organização grande sem a organização.

**Nx, Turborepo ou Bazel.** Resolvem grafo de dependência entre muitos pacotes da mesma linguagem. Aqui são duas apps isoladas, sem código compartilhado além de tipos gerados. Nenhum problema concreto justifica.

## Consequências

- Commit atômico quando o contrato da API e o client mudam junto.
- O gate de OpenAPI em CI deixa de ser necessário: quebra de contrato falha no `tsc` do mesmo commit.
- CI precisa de filtro por path para não rodar Playwright em mudança de Python. Custo: configuração inicial de uma vez.
- Filtro por path cria um bloqueio de merge conhecido: um PR que só toca uma pasta nunca reporta o check da outra, e um required check que não roda travava o PR. Mitigação adotada: apenas um job agregador é marcado como required; ele sempre roda e trata `skipped` como sucesso.
- Deploy independente por app exige que o pipeline saiba qual pasta mudou. Não é automático como em repos separados.

## O que me faria reverter

Fechar o primeiro cliente e precisar de cadência de release realmente independente entre API e painel — versionamento separado, hotfix na API sem tocar no front.

A reversão é conhecida e barata: `git subtree split` extrai `api/` preservando histórico. Estimativa de uma tarde. A assimetria favorece começar junto: separar depois é mecânico, unificar depois é reescrever histórico.
