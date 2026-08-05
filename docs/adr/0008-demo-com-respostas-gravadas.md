# ADR-0008 — Demo pública com respostas gravadas

**Status:** Proposto — não confirmado
**Data:** 2026-08-05

## Contexto

O repositório é público e uma demo acessível aumenta muito o valor como case: quem avalia abre um link em vez de clonar.

O ponto que precisa ficar explícito: se a demo responde, existe credencial real naquele servidor. Não há terceira opção. Ou a demo chama LLM de verdade e alguém desconhecido gasta token por nossa conta, ou ela não chama LLM nenhuma.

Agrava o caso o fato de que a demo é um painel de **edição**. Público e sem autenticação, qualquer visitante altera agentes, renomeia e publica versão nova.

## Decisão proposta

Demo funcional com respostas de inferência gravadas. Fixtures capturadas uma vez em desenvolvimento; o backend replaya na demo. O painel de edição — validação, linter, capabilities, versionamento — roda de verdade; apenas a inferência é replay.

Banco isolado com seed fictício e restauração periódica automatizada.

## Alternativas descartadas

**Demo ao vivo com chave real.** O modo de falha é ruim: avaliador abre o link, cota esgotada, tela vazia. Demo que sempre funciona vale mais que demo autêntica que às vezes funciona — e ninguém observando a tela distingue token gerado agora de fixture.

Se um dia for ao vivo, o controle que importa não está no nosso código: é limite de gasto configurado no console do provedor, em projeto e chave dedicados apenas à demo. Em cima disso, login obrigatório, rate limit por usuário, modelo barato fixo, `max_tokens` curto e nenhuma tool com acesso a rede ou a dinheiro.

**Nenhuma demo.** Reduz muito o valor de case. Quem avalia gasta poucos minutos e um link funcional é o artefato de maior retorno.

**Tenant efêmero por sessão de visitante.** Solução melhor que reset periódico, mas complexidade desnecessária agora. O reset cobre.

## Consequências

- Fixtures precisam ser gravadas e mantidas. Se o formato de evento de streaming do Agno mudar entre versões, o replay quebra.
- O seed fictício deve ser escrito como código. Não é trabalho descartável: é o mesmo script que provisiona cliente novo, exigido pelo ADR-0003.
- A demo é um deploy da **mesma** imagem, só com variáveis de ambiente diferentes. Se ela precisar de código próprio, criou-se um segundo produto para manter.
- Segredos ficam no secret store da plataforma de deploy, nunca em arquivo commitado — mesmo com o código aberto. Visibilidade do código e visibilidade de credencial são coisas separadas.
- Perde-se autenticidade: a demo não prova que a integração com o provider funciona. Isso precisa ser demonstrado por eval em CI, não pela demo.

## O que me faria reverter

Um interlocutor específico — cliente em negociação, não avaliador de portfólio — precisar interagir ao vivo com o agente. Nesse caso, ambiente separado, com login, cap de gasto no provedor e prazo de validade, em vez de abrir a demo pública.

## Nota de segurança que não depende desta decisão

Histórico de git é público. Credencial commitada e removida no commit seguinte permanece acessível para sempre, e bots varrem o GitHub em minutos. Antes do primeiro commit de código: `gitleaks` como hook de pre-commit, `.gitignore` cobrindo `.env*` e arquivos de chave, e secret scanning com push protection habilitado. Após vazamento, rotacionar a credencial é obrigatório — reescrever histórico não resolve, porque a cópia já saiu.
