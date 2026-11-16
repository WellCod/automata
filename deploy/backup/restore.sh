#!/bin/sh
# Restaura um dump do bucket num banco vazio. Passo a passo em docs/restauracao.md.
#   restore.sh daily/automata-2026-11-16T030000Z.dump.enc
# Mesmas variáveis do backup.sh; PGDATABASE precisa existir e estar vazio.
set -eu

: "${1:?informe o caminho do dump no bucket, por exemplo daily/automata-....dump.enc}"
: "${BACKUP_BUCKET:?defina BACKUP_BUCKET}"
: "${BACKUP_PASSPHRASE:?defina BACKUP_PASSPHRASE}"
BUCKET="${BACKUP_BUCKET%/}"

if [ -n "${BACKUP_ENDPOINT_URL:-}" ]; then
  aws --endpoint-url "$BACKUP_ENDPOINT_URL" s3 cp --only-show-errors "$BUCKET/$1" /tmp/restore.enc
else
  aws s3 cp --only-show-errors "$BUCKET/$1" /tmp/restore.enc
fi
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_PASSPHRASE \
  -in /tmp/restore.enc -out /tmp/restore.dump
rm -f /tmp/restore.enc
# a extensão do pgvector é criada pelo próprio dump
pg_restore --no-owner --no-privileges --exit-on-error -d "$PGDATABASE" /tmp/restore.dump
rm -f /tmp/restore.dump
echo "restaurado $1 em $PGDATABASE"
