# ADR-0003 — Deploy single-tenant, uma instância por cliente

**Status:** Aceito
**Data:** 2026-08-05

## Contexto

O modelo de negócio previsto é contrato com taxa de implantação mais mensalidade, vendido a empresas — inclusive em domínios regulados, como cobrança e seguros. Não há tier auto-serviço planejado.

A alternativa natural seria multi-tenant: uma instância servindo N clientes, com isolamento lógico.

## Decisão

Uma instância completa por cliente — aplicação e banco dedicados. O Agno oferece templates de deploy prontos para Docker, AWS, GCP, Azure, Fly, Render, Modal, Railway e Kubernetes, todos equivalentes exceto o script de deploy.

## Alternativas descartadas

**Tabelas compartilhadas com `tenant_id`.** Uma cláusula `WHERE` esquecida é vazamento de dado entre clientes. Em setor regulado o dano não é bug, é contratual. O custo de garantir escopo em toda query, todo cache e toda agregação é permanente e recai sobre cada feature nova.

**Schema por tenant em Postgres compartilhado.** Melhor que `tenant_id`, e era a recomendação inicial. Descartado porque isolamento físico é resposta estritamente melhor no questionário de segurança do cliente-alvo, e porque a taxa de implantação do modelo de negócio já paga o custo por instância.

**Banco por tenant com aplicação compartilhada.** Meio-caminho que herda o pior dos dois: pool de conexões não escala em N clientes e o código ainda precisa de roteamento por tenant.

## Consequências

- `user_isolation` do Agno passa a operar no nível correto: separar usuários **dentro** de um cliente, não clientes entre si.
- O isolamento vira argumento comercial. O cliente pode hospedar na própria cloud e o dado nunca sai.
- Taxa de implantação passa a corresponder a trabalho real.
- Surge o problema de frota. Três clientes se operam à mão; trinta não. Exige imagem versionada, deploy automatizado e rollout de migration em N instâncias. O Agno tem endpoints de migração, mas orquestrar entre instâncias é nosso.
- Piso de custo por cliente: banco e compute ociosos. Irrelevante em contrato enterprise, inviável em ticket baixo.
- Risco de deriva de versão: sem deploy automatizado, em 18 meses há seis versões em produção. É o modo de falha clássico deste modelo.
- O seed de tenant precisa ser código desde o primeiro cliente, não configuração manual — é o mesmo script que provisiona cliente novo.

## O que me faria reverter

Decidir lançar um tier auto-serviço de ticket baixo, onde o piso de custo por instância destrói a margem.

A reversão é caro: retrofit de escopo em cada query, tabela e cache. A assimetria é o oposto do ADR-0001 — aqui a migração posterior é a difícil. Mitigação adotada, que custa zero: não cravar premissa de instância única no código. Sem ID de cliente hardcoded, sem tabela de config de uma linha, sem estado global de cliente. Isso mantém a migração difícil em vez de impossível.
