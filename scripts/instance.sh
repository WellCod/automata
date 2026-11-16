#!/usr/bin/env bash
# Operação de uma instância de cliente com o docker-compose.yml de produção (OPS-04).
# Não interativo: tudo vem do ambiente ou de argumentos, para rodar por SSH ou CI.
#
#   scripts/instance.sh provision   cria o .env com chaves novas e sobe tudo
#       DOMAIN=agentes.cliente.com OWNER_EMAIL=ti@cliente.com AUTOMATA_VERSION=v1.5.0
#       (opcional: BACKUP_BUCKET, BACKUP_ENDPOINT_URL, BACKUP_ACCESS_KEY_ID, BACKUP_SECRET_ACCESS_KEY)
#   scripts/instance.sh upgrade v1.6.0   backup, troca a versão, sobe e confere o /health
#   scripts/instance.sh backup           um backup agora
#   scripts/instance.sh status           /health da instância
#
# Passo a passo em docs/atualizacao.md e docs/restauracao.md.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker-compose.yml)

log() { echo "instance: $*"; }
die() { echo "instance: $*" >&2; exit 1; }

profiles() {
  local out=(--profile tls)
  if grep -q '^BACKUP_BUCKET=.\+' .env 2>/dev/null; then out+=(--profile backup); fi
  echo "${out[@]}"
}

set_var() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env; then
    # | como separador: valores com / (URL) não quebram o sed
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >>.env
  fi
}

health() {
  local tries="${1:-30}"
  for _ in $(seq "$tries"); do
    if body="$("${COMPOSE[@]}" exec -T web wget -q -O - http://127.0.0.1:3000/api/health 2>/dev/null)"; then
      echo "$body"
      echo "$body" | grep -q '"status":"ok"' && return 0
    fi
    sleep 5
  done
  return 1
}

provision() {
  [ -f .env ] && die ".env já existe; provision é só para instância nova"
  : "${DOMAIN:?defina DOMAIN, o endereço do painel}"
  : "${OWNER_EMAIL:?defina OWNER_EMAIL, o primeiro owner}"
  command -v openssl >/dev/null || die "openssl não encontrado"
  local priv pub db_pass
  priv="$(openssl genrsa 2048 2>/dev/null)"
  pub="$(printf '%s\n' "$priv" | openssl rsa -pubout 2>/dev/null)"
  db_pass="$(openssl rand -hex 16)"
  # o PEM vai entre aspas duplas, com as quebras de linha: é assim que o compose lê
  grep -vE '^JWT_(PRIVATE|PUBLIC)_KEY=' .env.example >.env
  printf 'JWT_PRIVATE_KEY="%s"\nJWT_PUBLIC_KEY="%s"\n' "$priv" "$pub" >>.env
  set_var AUTOMATA_VERSION "${AUTOMATA_VERSION:-latest}"
  set_var POSTGRES_PASSWORD "$db_pass"
  set_var DATABASE_URL "postgresql+psycopg://automata:${db_pass}@db:5432/automata"
  set_var MCP_SECRETS_KEY "$(openssl rand -base64 32 | tr '+/' '-_')"
  set_var BACKUP_PASSPHRASE "$(openssl rand -base64 32)"
  set_var DOMAIN "$DOMAIN"
  set_var PUBLIC_URL "https://${DOMAIN}"
  for key in BACKUP_BUCKET BACKUP_ENDPOINT_URL BACKUP_ACCESS_KEY_ID BACKUP_SECRET_ACCESS_KEY; do
    [ -n "${!key:-}" ] && set_var "$key" "${!key}"
  done
  chmod 600 .env
  log ".env criado. Guarde fora desta máquina: JWT_PRIVATE_KEY, MCP_SECRETS_KEY e BACKUP_PASSPHRASE"
  # shellcheck disable=SC2046
  "${COMPOSE[@]}" $(profiles) pull
  # shellcheck disable=SC2046
  "${COMPOSE[@]}" $(profiles) up -d
  health 40 || die "a instância não ficou saudável; veja docker compose logs api"
  local password
  password="$(openssl rand -base64 18)"
  "${COMPOSE[@]}" exec -T -e SEED_OWNER_EMAIL="$OWNER_EMAIL" -e SEED_OWNER_PASSWORD="$password" \
    -e SEED_OWNER_MUST_CHANGE=true api python scripts/seed_owner.py
  log "owner $OWNER_EMAIL criado. Senha provisória (troca no primeiro login): $password"
}

backup() {
  grep -q '^BACKUP_BUCKET=.\+' .env || die "BACKUP_BUCKET vazio no .env"
  "${COMPOSE[@]}" --profile backup run --rm backup once
}

upgrade() {
  local version="${1:?informe a versão, por exemplo v1.6.0}"
  [ -f .env ] || die ".env não encontrado"
  if grep -q '^BACKUP_BUCKET=.\+' .env; then
    backup
  else
    log "sem BACKUP_BUCKET: atualizando sem backup"
  fi
  set_var AUTOMATA_VERSION "$version"
  # shellcheck disable=SC2046
  "${COMPOSE[@]}" $(profiles) pull
  # shellcheck disable=SC2046
  "${COMPOSE[@]}" $(profiles) up -d
  health 40 || die "a versão $version não ficou saudável; para voltar, veja docs/atualizacao.md"
  log "instância em $version"
}

case "${1:-}" in
  provision) provision ;;
  upgrade) upgrade "${2:-}" ;;
  backup) backup ;;
  status) health 1 ;;
  *) die "uso: instance.sh provision | upgrade <versão> | backup | status" ;;
esac
