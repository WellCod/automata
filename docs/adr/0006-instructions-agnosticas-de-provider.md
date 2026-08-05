# ADR-0006 — Instructions agnósticas de provider e modelo resolvido por identificador

**Status:** Aceito
**Data:** 2026-08-05

## Contexto

Requisito explícito do produto: trocar o modelo de IA de um agente deve ser alterar um campo, sem reescrever prompt. O Agno é agnóstico de provider e aceita qualquer modelo na construção do `Agent`, então a capacidade existe no framework.

O risco não está no framework. Está no conteúdo do prompt: uma instruction que diz "responda em JSON sem markdown" ou que menciona blocos de raciocínio está acoplada ao formato de um provider específico. Nesse caso o campo troca, mas o comportamento quebra — e quebra silenciosamente, com saída degradada em vez de erro.

## Decisão

Três regras, verificadas por teste:

1. Nenhuma seção de instruction contém formato ou terminologia específica de provider.
2. O modelo é referenciado por identificador (`model_id`) resolvido por um mapa para instância de `Model` do Agno.
3. Flags de capability são validadas contra uma matriz `model_id → capabilities` no momento da escrita.

O mapa constrói a instância de `Model` por request, não como singleton de módulo.

## Alternativas descartadas

**Confiar em revisão humana.** O acoplamento é sutil e entra por edição incremental de prompt em produção, feita por quem não conhece a regra. Precisa de gate automatizado.

**Aceitar prompt por provider.** Multiplica o número de prompts a manter pelo número de modelos, e destrói a premissa do requisito.

**Deixar a validação de capability em runtime.** Salvar uma configuração que só falha quando alguém conversa com o agente empurra o erro para o pior momento possível. Falha na escrita é preferível.

**Instância de `Model` como singleton no `Registry`.** É a forma mais óbvia e a mais barata, mas presume credencial única e global. Como o modelo comercial admite chave por cliente, singleton forçaria reescrita depois. O custo de construir por request é irrelevante frente a uma chamada de LLM.

## Consequências

- Teste que varre instructions contra uma lista de termos proibidos e falha o build.
- Matriz de capabilities precisa ser mantida à mão e fica desatualizada quando provider lança modelo novo. É dívida conhecida e aceita.
- A matriz é exposta em endpoint para o painel desabilitar checkbox de capability não suportada, com explicação. Sem isso o usuário salva configuração inválida e não entende a recusa.
- Instructions decompostas em seções nomeadas (persona, situação, tom, objetivo, guardrails) tornam a varredura viável e a edição legível. Essa decomposição é convenção nossa, não do Agno — ele aceita instruction como texto ou lista.
- Perde-se a possibilidade de otimização específica de provider, que às vezes melhora resultado de forma mensurável.

## O que me faria reverter

Se um cliente específico precisar de qualidade que só se obtém com prompt otimizado para um provider, e a diferença for mensurável em eval.

A reversão seria parcial e controlada: permitir override por agente, marcado explicitamente como acoplado, com o teste falhando de forma informativa em vez de bloqueante nesses casos. O que não se deve fazer é remover a regra geral por causa de uma exceção.
