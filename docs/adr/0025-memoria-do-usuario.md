# ADR-0025 — Memória do usuário entre sessões, por agente, com retenção, dados pessoais mascarados e direito de apagar

**Status:** Aceito
**Data:** 2026-10-21

## Contexto

O agente lembra o que foi dito na conversa atual: os últimos turnos (#134) e, com compactação, o resumo do resto (ADR-0019). Numa conversa nova, esquece tudo. O cliente que já disse o tamanho que veste, a cidade onde mora ou que prefere ser chamado pelo apelido repete isso a cada atendimento.

O ADR-0019 deixou a memória entre sessões para uma fase própria, porque o cuidado é outro: **fatos sobre a pessoa guardados além da conversa**.

Verificado no Agno 3.1.8 instalado:

- `Agent(update_memory_on_run=True)`. No fim do run, um `MemoryManager` pede ao modelo os fatos novos sobre o usuário e grava em `agno_memories`, no banco do Agno, por `user_id`. Por padrão o modelo é o do próprio agente. O consumo entra nos totais do run (`ModelType.MEMORY_MODEL`), e a nossa medição já registra.
- `add_memories_to_context` põe as memórias do usuário nas instruções do run.
- **A leitura é por usuário, não por agente.** `MemoryManager.read_from_db` chama `get_user_memories(user_id=...)` sem `agent_id`. Ligada em dois agentes, a memória que o agente de cobrança guardou aparece para o agente de vendas. A gravação guarda `agent_id`, e o banco filtra por ele quando pedido.
- **Run sem `user_id` vira o usuário `"default"`.** Todos os anônimos dividiriam as mesmas memórias.
- `memory_capture_instructions` orienta o que guardar. Nada impede o modelo de guardar CPF, cartão ou endereço se a conversa tiver.
- O AgentOS expõe rotas de memória (`/memories`), filtradas por usuário e com os escopos dele.

No código atual:

- O `user_id` do run é o do token: usuário do painel ou o `user_id` que o sistema integrado manda.
- `app/guardrails/pii.py` encontra e mascara CPF, CNPJ, cartão, e-mail e telefone (ADR-0013).
- O poller da API roda a cada minuto.

## Decisão

**Opcional por agente, versionado no payload.** A seção `memory` tem:

- `enabled`, desligado por padrão;
- `instructions`, até 500 caracteres: o que vale lembrar, por exemplo "preferências de entrega e tamanho";
- `retention_days`, de 1 a 365, padrão 90.

Como a compactação, a memória é comportamento do agente: passa por rascunho, publicação e suíte. Time recusa a seção na escrita (422), porque a memória do líder e a dos membros se misturariam. Fica para quando houver um uso claro.

**Memória de um agente é só dele.** O factory usa um `MemoryManager` próprio que lê pelo par usuário e agente (`get_user_memories(user_id, agent_id)`). Uma memória guardada pelo agente de cobrança nunca vai para o contexto do agente de vendas.

**Sem usuário, sem memória.** Run sem `user_id` roda com a memória desligada, e o mesmo vale para os runs da suíte de testes. O `"default"` do Agno juntaria pessoas diferentes, e a suíte encheria a memória de quem disparou o teste.

**Dados pessoais mascarados antes de gravar.**

- O banco que o `MemoryManager` recebe passa cada memória pela máscara de PII de todos os tipos, independente do guardrail do agente.
- As instruções de captura dizem para não guardar documento, cartão, senha nem dado de saúde.
- A máscara é a garantia. A instrução reduz o que chega até ela.

**Retenção.** De hora em hora, o poller apaga as memórias de cada agente com memória ligada que passaram de `retention_days` desde a última atualização. Desligar a memória num agente não apaga nada sozinho: as memórias ficam até vencer, ou até alguém apagar.

**Ver e apagar.**

- O owner vê e apaga as memórias de um agente, por usuário (`/api/v1/configs/{id}/memories`).
- Cada usuário vê e apaga as próprias, em todos os agentes (`/api/v1/me/memories`).
- "Apagar todas" de um usuário num agente atende o pedido de exclusão.
- As rotas `/memories` do AgentOS continuam lá. O painel não usa nenhuma delas.

## Alternativas descartadas

- **`LearningMachine` do Agno, que guarda perfil, fatos e aprendizados por usuário.** Ele aprende mais coisas, e cada uma é uma categoria a mais de dado pessoal guardado. A memória do usuário cobre o pedido com menos superfície.
- **Memória compartilhada entre os agentes da instância.** É conveniente, mas o cliente contou uma coisa ao agente de cobrança e não espera que o de vendas saiba. Compartilhar exigiria uma decisão explícita por par de agentes.
- **Memória pela tool `update_user_memory` (agentic memory).** O modelo decide no meio da conversa o que guardar e apagar, com uma chamada de tool visível ao usuário. Gravar no fim do run é previsível e passa pela máscara do mesmo jeito.
- **Guardar sem máscara e mascarar só na exibição.** O dado ficaria no banco. A máscara antes de gravar é o que permite dizer que a memória não guarda documento.

## Consequências

- O agente reconhece o cliente entre conversas no que foi pedido para lembrar.
- Cada run com memória ligada faz uma chamada de modelo a mais no fim, cobrada no agente.
- Memória é dado pessoal. A instância passa a guardar fatos sobre os usuários finais por até `retention_days`, e quem opera precisa avisar isso aos usuários.
- Mudar o modelo do agente muda também o modelo que extrai as memórias.
- Nenhuma migration nossa: as memórias ficam na tabela do Agno, que o entrypoint já migra.

## O que me faria reverter

- Memórias mascaradas com frequência a ponto de perder o útil (endereço de entrega, por exemplo). Nesse caso, a máscara passa a ter tipos configuráveis por agente, como o guardrail de PII.
- O Agno passar a filtrar a leitura por agente. Nesse caso, o `MemoryManager` próprio sai.
