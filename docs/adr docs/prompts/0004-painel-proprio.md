# ADR-0004 — Painel próprio; Control Plane apenas como ferramenta interna

**Status:** Aceito
**Data:** 2026-08-05

## Contexto

O Agno oferece duas interfaces prontas:

- **Control Plane** (`os.agno.com`): SaaS hospedado que conecta do browser direto ao runtime. Cobre chat, Studio, traces em árvore e waterfall, sessions, knowledge, memories, schedules, approvals, verificação de JWT e gestão de usuários com papéis. Papéis customizados são restritos ao plano Enterprise.
- **`agno-agi/agent-ui`**: template MIT em Next.js, TypeScript, Tailwind e shadcn/ui, auto-hospedável. Escopo é apenas chat — streaming, render de tool calls, reasoning steps, references e multimodal.

O produto precisa de um painel de gestão white-label, entregue ao cliente final.

## Decisão

Painel próprio para todas as telas de gestão. O `agent-ui` é forkado apenas para a superfície de chat e modo teste. O Control Plane fica como ferramenta interna, conectada às nossas instâncias.

## Alternativas descartadas

**Entregar o Control Plane ao cliente.** Expõe o fornecedor, exige conta Agno por cliente, e os papéis e o billing são da Agno, não nossos. Coloca um terceiro no meio da nossa relação comercial.

**Customizar o `agent-ui` até virar o painel.** Não é um ponto de partida para a tela de edição: ele não tem lista de agentes, formulário, versionamento nem comparação. Não se chega a essas telas partindo dele; são artefatos diferentes.

**Construir o chat do zero.** Streaming resiliente, render de tool call, reasoning steps e multimodal já estão resolvidos no `agent-ui`, na mesma stack que adotamos. Reescrever seria desperdício deliberado.

## Consequências

- Telas de lista, edição e versões são código nosso, do zero.
- Fork do `agent-ui` mantém histórico de git para permitir puxar upstream depois.
- A stack do painel é ditada pelo fork: Next.js, TypeScript, Tailwind, shadcn/ui. Isso é uma restrição aceita, não uma preferência estética.
- Observabilidade não precisa ser reimplementada: cada instância pode ser conectada como um OS separado no nosso Control Plane, e o cliente nunca vê. Duas ressalvas: o Control Plane conecta do browser ao runtime, então instância em VPC fechada não é alcançável; e não foi verificado se o plano da Agno limita o número de OS conectados.
- O `agent-ui` autentica com um único bearer token, incluindo via variável `NEXT_PUBLIC_*`, que é embutida no bundle do browser. Isso é escopo do template, não defeito — mas inviabiliza usá-lo como base de autenticação. Ver ADR-0005.

## O que me faria reverter

Se a Agno lançar o Control Plane em versão auto-hospedável e white-label, com papéis customizados fora do tier Enterprise. Nesse cenário, todas as telas de observabilidade e o Studio deixariam de ser código nosso, e valeria migrar mesmo com custo de reescrita.

Reverter parcialmente é viável hoje: se uma tela nossa de traces se mostrar pior que a do Control Plane e o cliente não exigir white-label total, dá para não construí-la.
