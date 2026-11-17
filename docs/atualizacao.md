# Atualização e volta de versão

Cada versão do Automata é uma tag `vX.Y.Z` com as imagens `ghcr.io/wellcod/automata-api` e `ghcr.io/wellcod/automata-web` publicadas pelo `publish.yml`. A instância escolhe a versão por `AUTOMATA_VERSION` no `.env`, e o `/health` (no painel, `/api/health`) mostra a versão, a revisão do git e a migration do banco.

## Atualizar

1. Leia as notas da release: migration nova, variável nova no `.env.example`, ação manual.
2. Faça um backup na hora e confira o envio (veja [restauracao.md](restauracao.md)):

   ```bash
   docker compose --profile backup run --rm backup once
   ```

3. Troque a versão e suba:

   ```bash
   sed -i 's/^AUTOMATA_VERSION=.*/AUTOMATA_VERSION=v1.5.0/' .env
   docker compose pull api web
   docker compose up -d
   ```

   O boot da API roda as migrations que faltam. Com duas réplicas subindo juntas, só uma migra por vez (`pg_advisory_lock`).

4. Confira `/api/health`: `version` nova, `migration` nova, `status` `ok`.

Ou, com o script: `scripts/instance.sh upgrade v1.5.0`, que faz os passos 2 a 4.

## Voltar uma versão

A imagem velha não conhece a migration nova e recusa subir com o banco à frente dela: o log da API diz `banco numa migration que esta imagem não conhece` com a revisão do banco e a da imagem. O downgrade sai com a imagem **nova**, que conhece as duas pontas.

1. Ainda na versão nova, veja a migration da versão de destino nas notas da release (ou rode `alembic heads` com a imagem velha).
2. Desça o banco com a imagem nova:

   ```bash
   docker compose run --rm --entrypoint alembic api downgrade 0058
   ```

3. Troque `AUTOMATA_VERSION` para a versão anterior e suba com `docker compose pull api web && docker compose up -d`.

Downgrade que apaga coluna perde o que foi gravado nela desde a atualização. Quando a volta é por falha grave logo depois de atualizar, restaurar o backup do passo 2 da atualização é mais seguro.

O CI roda `downgrade base` seguido de `upgrade head` em todo PR que muda a API, então toda migration tem caminho de volta testado.
