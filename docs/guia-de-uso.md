# Guia de uso

Para quem vai criar e operar agentes no painel, sem precisar ler o código.

## Papéis

- **Owner:** tudo, inclusive usuários, servidores MCP, canais, integrações, chaves, alertas, titulares e auditoria.
- **Editor:** cria, edita, testa e publica agentes, times e workflows; alimenta as bases de conhecimento; atende conversas dos canais.
- **Viewer:** consulta agentes, execuções e métricas, sem o conteúdo das conversas.

A senha criada pelo owner é provisória: no primeiro login a pessoa escolhe outra. Cada um troca a própria senha em "Trocar senha" e recupera pelo "Esqueci minha senha" do login.

## Primeiro agente

1. Em **Agentes**, crie do zero ou a partir de um exemplo.
2. Escolha o modelo (os que não têm chave configurada aparecem desabilitados) e escreva as instruções em seções: persona, situação, tom, objetivo e limites. Salve o rascunho.
3. Converse com ele no **modo teste**, à direita. Sem versão publicada, o teste usa o rascunho; depois, marque "Testar rascunho". As tools chamadas aparecem abaixo da conversa, e "Parar" interrompe a resposta.
4. Na aba **Versões**, publique. A versão publicada é a que integrações e canais usam. Rollback volta para uma versão anterior sem apagar nada; o canário manda parte das conversas para a versão nova antes.

Todo agente novo já nasce com limite de 20 mil caracteres por mensagem, exame do resultado das tools e no máximo 15 chamadas de tool por execução.

## O que mais configurar

- **Guardrails:** dados pessoais mascarados ou bloqueados, injeção de prompt, tópicos proibidos, classificador por modelo e regras da resposta.
- **Bases de conhecimento:** em Conhecimento, envie arquivos, URLs ou ligue conectores (GitHub, S3, SharePoint, Google Drive, Cloud Storage); depois vincule a base ao agente.
- **Ferramentas (MCP):** o owner cadastra o servidor; no agente, marque só as tools necessárias e peça confirmação nas que enviam ou alteram algo.
- **Testes:** na aba Testes, casos com o que o agente deve responder. A publicação pode exigir a suíte verde.
- **Controle do run:** limite de tools, teto de custo por execução, modelo reserva e compressão.

## Canais

Em **Canais** (owner), ligue um agente publicado a um número de WhatsApp ou app de Slack. Cada conversa começa com o aviso de primeiro contato, e quem manda "sair" encerra e tem os dados apagados. Quem pede atendente cai na fila de **Conversas**.

## Acompanhar

- **Execuções** (no agente): cada run com status, duração, custo e a árvore do que aconteceu; filtre por status e período.
- **Analytics:** volume, latência, custo e bloqueios; "Exportar consumo do mês" baixa o CSV para o financeiro.
- **Alertas:** destinos (webhook, e-mail) para orçamento, pico de erro, suíte e pedidos do titular.
- **Auditoria:** quem mudou o quê, logins e leituras de dado pessoal; exporta em CSV.

## Ajuda

A versão da instância aparece passando o mouse no rodapé do menu. Ao pedir suporte, informe a versão, o horário e o id da execução (na aba Execuções).
