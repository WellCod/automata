# Plano de resposta a incidentes — minuta

**Minuta para revisão jurídica e operacional.**

## O que conta como incidente

Acesso, divulgação, alteração ou perda não autorizada de dado pessoal ou de credencial da instância: token ou chave vazada, conta comprometida, backup exposto, agente que revelou dado de outra pessoa, provedor que comunicou incidente.

## Detecção

- Alertas da instância (página Alertas): pico de erro, orçamento estourado, pedido do titular falho ou vencendo.
- Trilha de auditoria: logins recusados em série, leituras de dado pessoal fora do padrão, mudança de papel, emissão de token.
- `/api/health` monitorado por fora (versão, banco, Redis, poller).
- Avisos de segurança das dependências (Dependabot, `pip-audit`, `pnpm audit`).

## Contenção (primeiras horas)

1. Revogar o que vazou: token de integração (Integrações), sessões do usuário (desativar ou trocar papel corta na hora), chave JWT ou de segredos ([rotacao-de-chaves.md](../rotacao-de-chaves.md), sem chave anterior quando a privada vazou).
2. Desligar o que expõe: canal, servidor MCP, conector ou agente envolvido.
3. Preservar evidência: exportar a trilha de auditoria (CSV) e os logs do período antes da retenção apagar.

## Comunicação

- Ao controlador (cliente): em até [48 horas] da ciência, com o que se sabe, os dados e titulares afetados, as medidas tomadas e o contato do encarregado.
- À ANPD e aos titulares: decisão e comunicação do controlador (art. 48), com o apoio do operador.

## Depois

Relatório com causa, linha do tempo, dados afetados e correção; teste que reproduz a falha; atualização deste plano.

## Contatos

Encarregado do operador: [NOME, e-mail, telefone]. Responsável técnico de plantão: [NOME, contato].
