# Backup e restauração

O estado de uma instância é o banco Postgres: agentes, versões, bases (com os vetores), conversas, runs, trilha de auditoria e segredos cifrados. Fora dele ficam três chaves que o operador guarda fora da VM: `JWT_PRIVATE_KEY`, `MCP_SECRETS_KEY` e `BACKUP_PASSPHRASE`. Sem a `MCP_SECRETS_KEY`, o banco restaurado volta sem conseguir ler as credenciais de MCP, conectores, canais e webhooks; sem a `BACKUP_PASSPHRASE`, o dump não abre.

## Backup

O serviço `backup` do `docker-compose.yml` (perfil `backup`) roda `pg_dump -Fc` todo dia na hora `BACKUP_HOUR` (UTC), cifra o arquivo com AES-256 e envia para `BACKUP_BUCKET/daily/`. Aos domingos o mesmo arquivo vai também para `weekly/`. Ficam os 7 diários e os 4 semanais mais recentes (`BACKUP_KEEP_DAILY`, `BACKUP_KEEP_WEEKLY`).

1. Crie um bucket fora desta máquina (S3, R2, B2, MinIO...) e uma chave com permissão de listar, gravar e apagar só nele.
2. Preencha no `.env`: `BACKUP_BUCKET`, `BACKUP_ENDPOINT_URL` (vazio na AWS), `BACKUP_ACCESS_KEY_ID`, `BACKUP_SECRET_ACCESS_KEY`, `BACKUP_REGION` e `BACKUP_PASSPHRASE`.
3. Suba com o perfil:

   ```bash
   docker compose --profile backup up -d
   ```

4. Rode um backup na hora para conferir o acesso ao bucket:

   ```bash
   docker compose --profile backup run --rm backup once
   ```

O log do serviço mostra cada envio e cada arquivo removido pela retenção. Uma falha não derruba o laço: tenta de novo no dia seguinte e fica no log.

## Restauração

Num banco vazio, na mesma versão da imagem da API que gerou o dump ou mais nova:

1. Suba só o banco, com volume novo:

   ```bash
   docker compose up -d db
   ```

2. Escolha o dump e restaure:

   ```bash
   docker compose --profile backup run --rm backup list
   docker compose --profile backup run --rm --entrypoint restore.sh backup daily/automata-2026-11-16T030000Z.dump.enc
   ```

   O `restore.sh` baixa o arquivo, decifra com a `BACKUP_PASSPHRASE` e roda `pg_restore` no `POSTGRES_DB`. A extensão do pgvector e o schema `ai` do Agno vêm do próprio dump.

3. Ponha no `.env` as mesmas `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY` e `MCP_SECRETS_KEY` da instância original e suba o resto:

   ```bash
   docker compose up -d
   ```

   O boot da API roda as migrations que faltarem, se a imagem for mais nova que o dump.

4. Confira o painel: login, lista de agentes, uma execução no modo teste e uma busca de teste numa base.

## Teste da restauração

Feito em 2026-11-16 com o banco do ambiente de prints (migration 0058): três backups seguidos com `BACKUP_KEEP_DAILY=2` deixaram os dois mais novos no bucket; o último foi restaurado num `pgvector/pgvector:pg17` vazio. A versão do Alembic, as contagens de `agent_config`, `agent_run`, `ai.agno_sessions`, `knowledge_content` e `audit_event` e os vetores da base bateram com a origem, e `python -m app.migrate` da imagem da API rodou sem nada a aplicar.

Repita o teste a cada atualização que mude o banco de forma relevante e pelo menos uma vez por trimestre em cada cliente.
