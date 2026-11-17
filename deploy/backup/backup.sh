#!/bin/sh
# Dump diário do Postgres para um bucket S3 compatível, com retenção.
#   backup.sh loop   roda todo dia na hora BACKUP_HOUR (UTC)
#   backup.sh once   um dump agora
#   backup.sh list   dumps guardados no bucket
# Variáveis: PGHOST, PGUSER, PGPASSWORD, PGDATABASE, BACKUP_BUCKET (s3://bucket/prefixo),
# BACKUP_ENDPOINT_URL (vazio = AWS), AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
# AWS_DEFAULT_REGION, BACKUP_PASSPHRASE (cifra o arquivo), BACKUP_KEEP_DAILY (7),
# BACKUP_KEEP_WEEKLY (4), BACKUP_HOUR (3).
set -eu

: "${BACKUP_BUCKET:?defina BACKUP_BUCKET, por exemplo s3://empresa-backups/automata}"
: "${BACKUP_PASSPHRASE:?defina BACKUP_PASSPHRASE: o dump tem dado pessoal e sai cifrado}"
KEEP_DAILY="${BACKUP_KEEP_DAILY:-7}"
KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-4}"
HOUR="${BACKUP_HOUR:-3}"
BUCKET="${BACKUP_BUCKET%/}"

aws_s3() {
  if [ -n "${BACKUP_ENDPOINT_URL:-}" ]; then
    aws --endpoint-url "$BACKUP_ENDPOINT_URL" s3 "$@"
  else
    aws s3 "$@"
  fi
}

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) backup: $*"; }

# apaga os mais antigos de um prefixo, mantendo os N mais recentes (nome com data ordena)
prune() {
  prefix="$1"
  keep="$2"
  aws_s3 ls "$BUCKET/$prefix/" | awk '{print $4}' | grep '\.dump\.enc$' | sort -r \
    | tail -n +"$((keep + 1))" | while read -r old; do
      aws_s3 rm "$BUCKET/$prefix/$old" >/dev/null
      log "removido $prefix/$old"
    done
}

once() {
  stamp="$(date -u +%Y-%m-%dT%H%M%SZ)"
  name="automata-$stamp.dump.enc"
  tmp="/tmp/$name"
  # -Fc: formato do pg_restore, comprimido; a cifra usa a senha do ambiente, nunca a linha
  pg_dump -Fc --no-owner --no-privileges \
    | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:BACKUP_PASSPHRASE -out "$tmp"
  size="$(wc -c <"$tmp")"
  aws_s3 cp --only-show-errors "$tmp" "$BUCKET/daily/$name"
  # domingo também vira semanal
  if [ "$(date -u +%u)" = "7" ]; then
    aws_s3 cp --only-show-errors "$tmp" "$BUCKET/weekly/$name"
  fi
  rm -f "$tmp"
  log "enviado daily/$name ($size bytes)"
  prune daily "$KEEP_DAILY"
  prune weekly "$KEEP_WEEKLY"
}

loop() {
  log "agendado para as ${HOUR}h UTC, guardando $KEEP_DAILY diários e $KEEP_WEEKLY semanais"
  while true; do
    now="$(date -u +%s)"
    today="$(date -u +%Y-%m-%d)"
    target="$(date -u -d "$today $(printf %02d "$HOUR"):00:00" +%s)"
    [ "$target" -le "$now" ] && target=$((target + 86400))
    sleep $((target - now))
    once || log "falhou; tenta de novo amanhã"
  done
}

case "${1:-loop}" in
  once) once ;;
  list) aws_s3 ls "$BUCKET/daily/"; aws_s3 ls "$BUCKET/weekly/" || true ;;
  loop) loop ;;
  *) echo "uso: backup.sh [once|loop|list]" >&2; exit 2 ;;
esac
