#!/usr/bin/env bash
# Deploy Automata → Railway (API + DB + Redis) + Vercel (painel)
# Uso: bash scripts/deploy.sh
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
ok()    { echo -e " ${GREEN}✓${NC} $*"; }
warn()  { echo -e " ${YELLOW}!${NC} $*"; }
fail()  { echo -e " ${RED}✗${NC} $*"; exit 1; }
step()  { echo -e "\n${BOLD}$*${NC}"; }
pause() { echo -e "\n${YELLOW}Pressione ENTER quando estiver pronto...${NC}"; read -r; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
KEYS_FILE=".deploy-keys"

# ─────────────────────────────────────────────────────────────────────────────
step "1/7 · Verificando pré-requisitos"
# ─────────────────────────────────────────────────────────────────────────────

missing=()
command -v openssl  >/dev/null 2>&1 || missing+=("openssl")
command -v railway  >/dev/null 2>&1 || missing+=("railway  → npm install -g @railway/cli")
command -v vercel   >/dev/null 2>&1 || missing+=("vercel   → npm install -g vercel")
command -v pnpm     >/dev/null 2>&1 || missing+=("pnpm     → npm install -g pnpm")

if [ ${#missing[@]} -gt 0 ]; then
  echo -e "\n  ${RED}Ferramentas ausentes:${NC}"
  printf '    %s\n' "${missing[@]}"
  echo
  echo "  Instale e rode o script novamente."
  exit 1
fi
ok "railway, vercel, openssl disponíveis"

# ─────────────────────────────────────────────────────────────────────────────
step "2/7 · Gerando chaves RSA"
# ─────────────────────────────────────────────────────────────────────────────

if [ -f "$KEYS_FILE" ]; then
  warn "Arquivo $KEYS_FILE já existe — reaproveitando chaves existentes"
  # shellcheck source=/dev/null
  source "$KEYS_FILE"
else
  echo "  Gerando par RSA 2048..."
  _PRIV_RSA=$(openssl genrsa 2048 2>/dev/null)
  _PUB_PEM=$(echo "$_PRIV_RSA" | openssl rsa -pubout 2>/dev/null)
  _PRIV_PKCS8=$(echo "$_PRIV_RSA" | openssl pkcs8 -topk8 -nocrypt 2>/dev/null)

  # RSA (para a API) e PKCS8 (para o BFF Next.js) — em uma linha com \n literal
  inline() { printf '%s' "$1" | awk 'NF {sub(/\r/, ""); printf "%s\\n", $0}'; }
  JWT_PRIVATE_KEY_API=$(inline "$_PRIV_RSA")
  JWT_PUBLIC_KEY=$(inline "$_PUB_PEM")
  JWT_PRIVATE_KEY_WEB=$(inline "$_PRIV_PKCS8")

  # Salva para não regenerar se o script for reexecutado
  cat > "$KEYS_FILE" <<EOF
JWT_PRIVATE_KEY_API="${JWT_PRIVATE_KEY_API}"
JWT_PUBLIC_KEY="${JWT_PUBLIC_KEY}"
JWT_PRIVATE_KEY_WEB="${JWT_PRIVATE_KEY_WEB}"
EOF
  chmod 600 "$KEYS_FILE"
  ok "Chaves geradas e salvas em $KEYS_FILE"
fi

# ─────────────────────────────────────────────────────────────────────────────
step "3/7 · Login Railway"
# ─────────────────────────────────────────────────────────────────────────────

if ! railway whoami >/dev/null 2>&1; then
  echo "  Abrindo login Railway no browser..."
  railway login
else
  ok "Já autenticado como: $(railway whoami)"
fi

# ─────────────────────────────────────────────────────────────────────────────
step "4/7 · Criando projeto Railway"
# ─────────────────────────────────────────────────────────────────────────────

echo "  Inicializando projeto Railway..."
echo
warn "No menu interativo:"
warn "  → Escolha 'Empty Project'"
warn "  → Nome sugerido: automata"
echo
railway init

ok "Projeto criado"

# ─────────────────────────────────────────────────────────────────────────────
step "5/7 · Provisionando PostgreSQL e Redis"
# ─────────────────────────────────────────────────────────────────────────────

echo "  Adicionando PostgreSQL..."
railway add --plugin postgresql
ok "PostgreSQL provisionado"

echo "  Adicionando Redis..."
railway add --plugin redis
ok "Redis provisionado"

# Aguarda Railway expor as variáveis de conexão
echo "  Aguardando variáveis de conexão ficarem disponíveis..."
DATABASE_URL=$(railway variables --service PostgreSQL --json 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('DATABASE_URL',''))" 2>/dev/null || true)
REDIS_URL=$(railway variables --service Redis --json 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('REDIS_URL',''))" 2>/dev/null || true)

if [ -z "$DATABASE_URL" ] || [ -z "$REDIS_URL" ]; then
  warn "Não foi possível ler as URLs automaticamente."
  echo
  echo "  Abra o dashboard Railway → seu projeto → serviço PostgreSQL"
  echo "  Copie o valor de DATABASE_URL e cole abaixo:"
  printf "  DATABASE_URL: "
  read -r DATABASE_URL
  echo
  echo "  Agora abra o serviço Redis e cole o REDIS_URL:"
  printf "  REDIS_URL: "
  read -r REDIS_URL
fi

ok "DATABASE_URL: ${DATABASE_URL:0:40}..."
ok "REDIS_URL:    ${REDIS_URL:0:40}..."

# ─────────────────────────────────────────────────────────────────────────────
step "6/7 · Deploy da API no Railway"
# ─────────────────────────────────────────────────────────────────────────────

echo "  Configurando serviço API..."
echo

warn "No menu interativo que aparecer, selecione ou crie o serviço 'api'"
echo

# Aponta para o diretório da API
cd api

# Configura variáveis de ambiente da API
echo "  Configurando variáveis de ambiente..."
railway variables set \
  DATABASE_URL="$DATABASE_URL" \
  JWT_PRIVATE_KEY="$JWT_PRIVATE_KEY_API" \
  JWT_PUBLIC_KEY="$JWT_PUBLIC_KEY" \
  REDIS_URL="$REDIS_URL" \
  LOG_LEVEL="INFO" \
  DEMO_REPLAY="true"

ok "Variáveis configuradas"

echo "  Fazendo deploy da API..."
railway up --detach
ok "API em deploy (pode levar 2-3 minutos)"

echo "  Aguardando API ficar disponível..."
railway domain
API_URL=$(railway domain --json 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('https://'+d.get('domain',''))" 2>/dev/null || true)

if [ -z "$API_URL" ]; then
  warn "Cole a URL pública da API (Railway Dashboard → API → Settings → Networking):"
  printf "  API_URL (ex: https://automata-api.up.railway.app): "
  read -r API_URL
fi

ok "API URL: $API_URL"

cd "$ROOT"

# ─────────────────────────────────────────────────────────────────────────────
# Seed de produção
# ─────────────────────────────────────────────────────────────────────────────

echo
echo -e "  ${BOLD}Credenciais do usuário admin:${NC}"
printf "  Email (ex: admin@seudominio.com): "
read -r SEED_EMAIL
printf "  Senha (mín. 8 chars, 1 maiúscula, 1 número, 1 especial): "
read -r SEED_PASSWORD

echo "  Rodando seed full (owner + 5 agentes + 500 runs)..."
railway run --service api \
  bash -c "SEED_OWNER_EMAIL='$SEED_EMAIL' SEED_OWNER_PASSWORD='$SEED_PASSWORD' .venv/bin/python scripts/seed.py full" \
  2>/dev/null || {
    warn "Seed via railway run falhou — rode manualmente após o deploy:"
    warn "  railway run bash -c \"SEED_OWNER_EMAIL='$SEED_EMAIL' SEED_OWNER_PASSWORD='$SEED_PASSWORD' .venv/bin/python scripts/seed.py full\""
  }

# ─────────────────────────────────────────────────────────────────────────────
step "7/7 · Deploy do painel no Vercel"
# ─────────────────────────────────────────────────────────────────────────────

cd "$ROOT/web"

echo "  Iniciando deploy Vercel..."
echo
warn "No menu interativo do Vercel:"
warn "  → 'Set up and deploy'"
warn "  → Confirm o diretório: web/"
warn "  → Framework: Next.js (detectado automático)"
echo

vercel --yes 2>/dev/null || vercel

echo
echo "  Configurando variáveis de ambiente no Vercel..."
echo "$API_URL"          | vercel env add AUTOMATA_API_URL production
echo "$JWT_PRIVATE_KEY_WEB" | vercel env add JWT_PRIVATE_KEY production
echo "automata"          | vercel env add JWT_AUDIENCE production
echo "panel"             | vercel env add PANEL_USER_ID production

echo "  Redeploy com as variáveis..."
vercel --prod --yes

ok "Painel publicado"

cd "$ROOT"

# ─────────────────────────────────────────────────────────────────────────────
step "Deploy concluído"
# ─────────────────────────────────────────────────────────────────────────────

WEB_URL=$(vercel ls --json 2>/dev/null | \
  python3 -c "import sys,json; items=json.load(sys.stdin); print('https://'+items[0].get('url',''))" 2>/dev/null || true)

echo
echo -e "  ${GREEN}API:    ${NC}$API_URL"
echo -e "  ${GREEN}Painel: ${NC}${WEB_URL:-'(veja o output do Vercel acima)'}"
echo
echo -e "  ${BOLD}Login:${NC}"
echo -e "  Email: $SEED_EMAIL"
echo -e "  Senha: (a que você definiu)"
echo
echo -e "  ${YELLOW}Chaves RSA salvas em: $ROOT/$KEYS_FILE${NC}"
echo -e "  ${YELLOW}Guarde esse arquivo. Você precisará das chaves se recriar os serviços.${NC}"
echo
warn "DEMO_REPLAY=true — respostas são fixtures, sem custo de LLM."
warn "Para usar LLM real: railway variables set DEMO_REPLAY=false (+ configure ANTHROPIC_API_KEY)"
echo
