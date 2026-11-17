# Acordo de tratamento de dados (DPA) — minuta

**Minuta para revisão jurídica. Os trechos entre colchetes são a preencher.**

## 1. Partes e papéis

[CLIENTE], controlador, e [FORNECEDOR], operador, acordam o tratamento de dados pessoais realizado pela plataforma Automata, instalada em instância dedicada ao CLIENTE.

## 2. Objeto

O operador trata dados pessoais apenas para executar os agentes configurados pelo controlador, manter a instância (backup, atualização, suporte) e cumprir obrigação legal. Não usa os dados para finalidade própria nem para treinar modelos.

## 3. Dados e titulares

Categorias de titulares e de dados definidas pelo controlador ao configurar os agentes, canais e bases de conhecimento: em regra, clientes e colaboradores do controlador; nome, contato, histórico de conversa e o que o titular informar. O controlador não deve configurar agentes para tratar dado sensível (art. 11) sem base legal e sem avisar o operador.

## 4. Instruções do controlador

As configurações feitas no painel (agentes, guardrails, retenção, canais, integrações) são as instruções documentadas do controlador. Instrução que o operador considerar ilícita é comunicada antes de ser cumprida.

## 5. Suboperadores

Lista em [suboperadores.md](suboperadores.md). Inclusão ou troca é avisada com [30] dias de antecedência, e o controlador pode se opor.

## 6. Transferência internacional

Os provedores de modelo e de embedding processam dados fora do Brasil. A transferência se apoia em [cláusulas-padrão contratuais / outra hipótese do art. 33 — definir com o jurídico]. O controlador pode restringir os provedores ligados à instância.

## 7. Segurança

Medidas mínimas: instância isolada por cliente; TLS; segredos cifrados (Fernet) com rotação; senhas com argon2 e troca obrigatória da senha provisória; SSO opcional; papéis com menor privilégio; trilha de auditoria de escritas, logins e leituras de dado pessoal; mascaramento de dado pessoal na memória e, quando configurado, na entrada, na saída e nos argumentos de tool; backup diário cifrado fora da máquina.

## 8. Direitos do titular

A plataforma oferece consulta, exportação e exclusão por titular (página Titulares), com prazo de [15] dias e aviso de vencimento. O operador apoia o controlador nos pedidos que a plataforma não cobre sozinha.

## 9. Incidentes

Procedimento em [incidentes.md](incidentes.md). O operador comunica o controlador em até [48 horas] da ciência de incidente que possa acarretar risco ou dano relevante.

## 10. Retenção e término

Conversas e execuções seguem a retenção configurada (`CONVERSATION_RETENTION_DAYS`). No término do contrato, o operador entrega uma exportação em [formato] e apaga a instância e os backups em até [30] dias, salvo obrigação legal.

## 11. Auditoria

O controlador pode pedir evidências de cumprimento (trilha de auditoria exportada, relatório de pedidos do titular) [uma vez por ano / com aviso de 30 dias].

## 12. Encarregado

Encarregado do operador: [NOME, e-mail]. Encarregado do controlador: [NOME, e-mail].
