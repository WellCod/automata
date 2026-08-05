# ADR-0007 — Código aberto sob AGPL-3.0 com licença comercial paralela

**Status:** Proposto — não confirmado
**Data:** 2026-08-05

## Contexto

O repositório é público, com dois objetivos: servir como case técnico avaliável e, eventualmente, virar produto vendido.

Isso cria tensão. Código público não se torna privado de forma retroativa: forks sobrevivem e quem leu já leu. Ao mesmo tempo, repositório público **sem** arquivo de licença significa todos os direitos reservados — legalmente ninguém pode usar, modificar ou executar. Isso anula o valor de case, porque nem rodar a demo é permitido.

Sobre a dependência: o README atual do Agno declara Apache-2.0, e a listagem da organização confirma Apache-2.0 nos templates de deploy. Fontes anteriores — PyPI 1.1.6 e o próprio arquivo `LICENSE` — indicam MPL-2.0, o que sugere relicenciamento em algum momento. Ambas permitem produto fechado e revenda; a MPL exigiria manter abertos os arquivos do Agno que fossem modificados. Nenhuma das duas restringe o licenciamento do nosso código.

## Decisão proposta

AGPL-3.0 no repositório público, com licença comercial vendida em paralelo.

## Alternativas descartadas

**MIT ou Apache-2.0.** Qualquer um pode fechar, renomear e revender sem contrapartida. Aceitável se o objetivo fosse apenas portfólio; incompatível com intenção de venda.

**Sem arquivo de licença.** Mata o valor de case, como acima.

**Repositório privado.** O objetivo primário atual é portfólio, e repositório privado só aparece no gráfico de contribuições de forma anonimizada. Não serve de vitrine.

## Consequências

- AGPL obriga quem rodar o código como serviço de rede a abrir suas modificações, o que torna o fork comercialmente pouco atraente.
- A licença comercial é o outro lado do desenho: cliente que não aceita AGPL compra a exceção. É o mesmo modelo que a Agno pratica.
- **Isso só funciona se houver titularidade de 100% do código.** Contribuição externa sem cessão de direitos inviabiliza vender a exceção. Consequência prática: exigir cessão antes de aceitar o primeiro PR de terceiro.
- Risco comercial real: muitas empresas grandes têm proibição geral de AGPL no jurídico. Se o cliente-alvo for banco ou seguradora, isso pode travar negócio antes da avaliação técnica. É precisamente por isso que a licença comercial não é opcional no plano.
- A versão do Agno pinada e a licença verificada nela devem constar no README, porque a licença mudou historicamente.

## Pendências antes de aceitar

- Confirmar o `LICENSE` do Agno na versão que for pinada.
- Verificar cláusula de propriedade intelectual em contrato de trabalho vigente: código escrito em horário, máquina ou infraestrutura de empregador pode não ser do autor. É cláusula comum em contrato de tecnologia.
- Nada de dado real entra no repositório público: sem nome de cliente, sem prompt de produção, sem captura de tela com dado verdadeiro. Seeds fictícios.

Nenhum dos pontos acima é aconselhamento jurídico. Se virar receita, cabe uma consulta com advogado.

## O que me faria reverter

Perder negócio concreto por causa da AGPL, com a licença comercial não resolvendo a objeção do jurídico do cliente. Nesse caso, avaliar mudar para Apache-2.0 e depender de serviço e operação como fosso — que é, de todo modo, o que sustenta este modelo de negócio.

Reverter para licença mais permissiva é sempre possível. O caminho inverso não é: o que já foi distribuído sob MIT permanece MIT.
