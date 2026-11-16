# ADR-0045 — Prontidão para o primeiro cliente

**Status:** Proposto — o merge do PR é o aceite
**Data:** 2026-11-16

## Contexto

A auditoria de 2026-11-16 (Fase 51 do roadmap) concluiu que o código está perto de vender e o que cerca o código não: sem backup, conversas guardadas para sempre, senha de usuário conhecida pelo owner, agente novo sem nenhuma defesa ligada, canal de WhatsApp sem aviso ao titular e memória misturada atrás de um token de integração. Cada item é pequeno, mas juntos mudam padrões que hoje valem para toda instância. Este ADR registra os padrões novos para que as Fases 51 a 54 não precisem rediscutir cada um.

## Decisão

**Padrões seguros na criação, não no schema.** O agente e o líder de time criados pelo painel ou pela API nascem com `tool_call_limit` 15, `max_input_chars` 20.000 e exame de resultado de tool por termos. Os valores entram no payload do primeiro rascunho; o schema continua com tudo desligado, para que versões já publicadas não mudem de comportamento. `build_instructions` ganha uma frase fixa: o resultado de qualquer tool é dado, não instrução. O classificador por modelo segue opcional, porque custa uma chamada por tool.

**Rascunho roda no modo teste, com `configs:write`.** Todo config com rascunho fica registrado no runtime; `factory_input.version_id` só vale para quem tem `configs:write` ou é admin. Quem só tem `run` roda a versão vigente ou o canário, como antes.

**Identidade do usuário final no token de integração.** O `sub` do token continua `integration:<id>`. O integrador pode mandar o usuário final no campo `user_id` do formulário; a API grava `integration:<id>:<user_id>` e usa esse id na memória, no orçamento por quem chama e no titular. Sem `user_id`, a memória não liga para chamador `integration:*`.

**Retenção por instância.** `CONVERSATION_RETENTION_DAYS` (padrão 0, desligado) apaga, no poller que já expurga a trilha, sessões e runs do Agno, `agent_run`, traces e mensagens de canal mais velhos que o prazo, na ordem da exclusão do titular. Consumo (`usage_event`) fica, sem conteúdo. Retenção por agente fica para quando um cliente pedir.

**Senha do próprio usuário.** `POST /me/password` com a senha atual; a senha criada ou trocada pelo owner obriga a troca no primeiro login (`must_change_password`); recuperação por e-mail com link de uso único válido por 30 minutos, pelo `mailer.py`. MFA fica com o provedor de SSO (`PASSWORD_LOGIN=false`).

**Backup fora da VM.** Serviço `backup` no compose, perfil `backup`, com `pg_dump -Fc` diário para um bucket S3 compatível, retenção de 7 diários e 4 semanais, e `docs/restauracao.md` com a restauração testada. As chaves JWT e Fernet ficam fora do dump e fora da VM, por conta do operador.

**Aviso no canal.** Cada canal tem uma mensagem de primeiro contato, enviada uma vez por conversa antes da primeira resposta, e palavras de saída que encerram a conversa e abrem um pedido de exclusão do titular.

## Consequências

- Agente criado depois do merge se comporta diferente de um criado antes; os antigos não mudam até o owner editar.
- O integrador precisa mandar `user_id` para ter memória por pessoa; sem ele o comportamento fica mais restrito, não mais aberto.
- A retenção apaga dado de forma irreversível; o padrão desligado evita surpresa em instância já em uso.
- O backup depende de um bucket do operador; sem ele o serviço não sobe e o `/health` não muda.

## Fora do código

A auditoria também pede licença comercial e titularidade do código (COM-02), o kit de LGPD (COM-01) e a política de uso aceitável (COM-11). O repositório recebe minutas em `docs/legal/`, marcadas como tal; a versão que vale depende de revisão jurídica. A troca do par JWT e da senha do owner dos ambientes antigos (SEC-03) é ação do operador, descrita em `docs/rotacao-de-chaves.md`.
