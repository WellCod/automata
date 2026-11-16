# Suboperadores — minuta

**Minuta para revisão jurídica.** A lista real de cada instância depende das chaves configuradas no `.env`: provedor sem chave não recebe nada.

| Suboperador | Finalidade | Dados enviados | País | Quando entra |
|---|---|---|---|---|
| Anthropic | Modelo de linguagem (Claude) | Instruções do agente, mensagens, resultado de tools e trechos das bases | EUA | `ANTHROPIC_API_KEY` |
| OpenAI | Modelo de linguagem, embedding e moderação | Idem; textos das bases para embedding | EUA | `OPENAI_API_KEY` |
| Voyage AI | Embedding das bases de conhecimento | Textos dos documentos e perguntas de busca | EUA | `VOYAGE_API_KEY` |
| Cohere | Reordenação de trechos (cross-encoder) | Pergunta e trechos candidatos | EUA / Canadá | `COHERE_API_KEY` e base com cross-encoder Cohere |
| AWS (Bedrock, S3) | Reordenação de trechos; conector S3; bucket de backup | Pergunta e trechos; arquivos do bucket; dump cifrado | Região configurada | `AWS_REGION`, conector S3, `BACKUP_BUCKET` |
| Meta (WhatsApp Cloud API) | Canal de conversa | Número e mensagens do titular | EUA | Canal WhatsApp cadastrado |
| Slack | Canal de conversa | Id do usuário e mensagens | EUA | Canal Slack cadastrado |
| Provedor de e-mail (SMTP do cliente) | Avisos e recuperação de senha | E-mail do destinatário, texto do aviso | [definir] | `SMTP_HOST` |
| Provedor de OTLP | Traces de observabilidade | Sem conteúdo da conversa por padrão; com `OTEL_EXPORT_CONTENT=true`, o conteúdo | [definir] | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Hospedagem da VM | Infraestrutura da instância | Tudo o que a instância guarda | [definir] | Sempre |

`EXTRA_MODELS` com `base_url` própria (Azure OpenAI e afins) acrescenta o provedor daquela URL à lista.
