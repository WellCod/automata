#!/usr/bin/env bash
# Bootstrap do ambiente de desenvolvimento local.
# Idempotente: reexecuta sem destruir configuração existente.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; BOLD='\033[1m'; NC='\033[0m'
ok()    { echo -e "  ${GREEN}ok${NC}"; }
skip()  { echo -e "  já existe, pulando"; }
fail()  { echo -e "  ${RED}$*${NC}"; exit 1; }
step()  { printf "%-48s" "  $1"; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo
echo -e "${BOLD}automata — bootstrap${NC}"
echo

# ── 1. ferramentas ───────────────────────────────────────────────────────────
step "verificando ferramentas"
missing=()
command -v docker  >/dev/null 2>&1 || missing+=("docker")
command -v uv      >/dev/null 2>&1 || missing+=("uv       → https://docs.astral.sh/uv/")
command -v pnpm    >/dev/null 2>&1 || missing+=("pnpm     → npm install -g pnpm")
command -v openssl >/dev/null 2>&1 || missing+=("openssl")
if [ ${#missing[@]} -gt 0 ]; then
  echo
  echo -e "  ${RED}ferramentas ausentes:${NC}"
  printf '    %s\n' "${missing[@]}"
  exit 1
fi
ok

# ── 2. par RSA ───────────────────────────────────────────────────────────────
step "gerando par RSA 2048"
_PRIV_PEM=$(openssl genrsa 2048 2>/dev/null)
_PUB_PEM=$(echo "$_PRIV_PEM" | openssl rsa -pubout 2>/dev/null)
_PRIV_PKCS8=$(echo "$_PRIV_PEM" | openssl pkcs8 -topk8 -nocrypt 2>/dev/null)
_DB_PASS=$(openssl rand -hex 16)

# converte PEM multi-linha para uma linha com \n literal (lido por python-dotenv)
inline() { printf '%s' "$1" | awk 'NF {sub(/\r/, ""); printf "%s\\n", $0}'; }
PRIV_INLINE=$(inline "$_PRIV_PEM")
PUB_INLINE=$(inline "$_PUB_PEM")
PRIV_PKCS8_INLINE=$(inline "$_PRIV_PKCS8")
ok

# ── 3. .env (docker-compose) ─────────────────────────────────────────────────
step ".env"
if [ ! -f .env ]; then
  {
    printf 'POSTGRES_DB=automata\n'
    printf 'POSTGRES_USER=automata\n'
    printf 'POSTGRES_PASSWORD=%s\n\n' "$_DB_PASS"
    printf 'DATABASE_URL=postgresql+psycopg://automata:%s@db:5432/automata\n\n' "$_DB_PASS"
    printf 'JWT_PRIVATE_KEY=%s\n' "$PRIV_INLINE"
    printf 'JWT_PUBLIC_KEY=%s\n\n' "$PUB_INLINE"
    printf 'AUTOMATA_API_URL=http://localhost:8000\n'
  } > .env
  echo -e "  ${GREEN}criado${NC}"
else
  skip
fi

# ── 4. api/.env (uvicorn local sem Docker) ───────────────────────────────────
step "api/.env"
if [ ! -f api/.env ]; then
  {
    printf 'DATABASE_URL=postgresql+psycopg://automata:%s@localhost:5432/automata\n' "$_DB_PASS"
    printf 'JWT_PRIVATE_KEY=%s\n' "$PRIV_INLINE"
    printf 'JWT_PUBLIC_KEY=%s\n' "$PUB_INLINE"
  } > api/.env
  echo -e "  ${GREEN}criado${NC}"
else
  skip
fi

# ── 5. web/.env.local ────────────────────────────────────────────────────────
step "web/.env.local"
if [ ! -f web/.env.local ]; then
  {
    printf 'AUTOMATA_API_URL=http://localhost:8000\n'
    printf 'JWT_PRIVATE_KEY=%s\n' "$PRIV_PKCS8_INLINE"
    printf 'JWT_AUDIENCE=automata\n'
    printf 'PANEL_USER_ID=panel\n'
  } > web/.env.local
  echo -e "  ${GREEN}criado${NC}"
else
  skip
fi

# ── 6. dependências ───────────────────────────────────────────────────────────
step "uv sync"
(cd api && uv sync --quiet 2>/dev/null)
ok

step "pnpm install"
pnpm install --silent 2>/dev/null
ok

# ── 7. banco + migrations ────────────────────────────────────────────────────
step "postgres (docker)"
docker compose up db -d --wait --quiet-pull 2>/dev/null
ok

step "alembic upgrade head"
(cd api && uv run alembic upgrade head 2>&1 | grep -v "^$" || true)
ok

# ── 8. próximos passos ───────────────────────────────────────────────────────
echo
echo -e "${BOLD}Pronto.${NC} Próximos passos:"
echo
echo "  just dev       API + banco com hot reload"
echo "  just dev-web   painel Next.js (segunda sessão)"
echo "  just seed      seed inicial (defina SEED_OWNER_EMAIL e SEED_OWNER_PASSWORD)"
echo
