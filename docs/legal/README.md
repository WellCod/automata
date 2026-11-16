# Documentos jurídicos — minutas

**Minutas para revisão jurídica. Não usar com cliente antes da revisão por advogado.** Nada aqui é parecer jurídico.

No modelo de instância por cliente, o cliente é o **controlador** dos dados pessoais que trafegam nos agentes, e o fornecedor do Automata é **operador** (LGPD, art. 5º, VI e VII). Os documentos abaixo são o que o jurídico de um cliente B2B costuma pedir antes de assinar (auditoria de 2026-11-16, COM-01 e COM-11).

| Documento | Para quê | Estado |
|---|---|---|
| [dpa.md](dpa.md) | Acordo de tratamento de dados entre cliente (controlador) e fornecedor (operador) | Minuta |
| [suboperadores.md](suboperadores.md) | Quem mais trata dado pessoal, em que país e para quê | Minuta, depende da configuração da instância |
| [incidentes.md](incidentes.md) | Como o fornecedor detecta, contém e comunica incidente de segurança | Minuta |
| [uso-aceitavel.md](uso-aceitavel.md) | O que o cliente não pode fazer com os agentes | Minuta |

## Pendências que não são de código

- **Licença e titularidade (COM-02).** O [ADR-0007](../adr/0007-licenciamento.md) segue proposto: confirmar a licença do Agno, a titularidade do código (cláusula de propriedade intelectual em contrato de trabalho) e redigir a licença comercial paralela à AGPL. Sem isso não há o que licenciar.
- **Encarregado (DPO).** Nome e contato do encarregado do fornecedor, a preencher no DPA e no plano de incidentes.
- **Links no login.** Política de privacidade e termos de uso do cliente entram no rodapé do login quando existirem (variáveis a criar junto com a versão final).

## Onde cada dado fica

O inventário técnico está no [ADR-0032](../adr/0032-direitos-do-titular.md) e no README da API (seção "Direitos do titular"). A retenção é configurável (`CONVERSATION_RETENTION_DAYS`, `AUDIT_RETENTION_DAYS`, retenção da memória por agente) e o backup sai cifrado para o bucket do operador ([restauracao.md](../restauracao.md)).
