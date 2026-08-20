#!/usr/bin/env bash
# Atualiza PKF na VPS (git pull + rebuild). Preserva .env e volumes.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
PROFILE="${PROFILE:-router}"

cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "Erro: $APP_DIR/.env não existe. Copie .env.production.example primeiro."
  exit 1
fi

echo "==> Backup docker-compose local (se houver diff)"
if git diff --quiet docker-compose.yml 2>/dev/null; then
  echo "docker-compose.yml igual ao repo"
else
  cp docker-compose.yml "docker-compose.yml.bak.$(date +%Y%m%d%H%M%S)"
  git checkout -- docker-compose.yml
fi

echo "==> Git pull"
git pull origin main

echo "==> Mesclar .env (preserva GROQ/GEMINI/NINEROUTER existentes)"
bash deploy/hostinger/set-env-keys.sh

echo "==> Porta 8765 exposta (acesso externo)"
if grep -q '127.0.0.1:8765:8765' docker-compose.yml; then
  sed -i 's/127.0.0.1:8765:8765/8765:8765/' docker-compose.yml
fi

echo "==> OmniRoute/9Router no .env (se ainda faltar URL)"
grep -q '^NINEROUTER_URL=' .env || cat >> .env << 'EOF'

# OmniRoute router-only (340+ provedores via dashboard)
ROUTER_IMAGE=diegosouzapw/omniroute:latest
PKF_ROUTER_ONLY=1
NINEROUTER_URL=http://ninerouter:20128
PKF_PROVIDER=ninerouter
PKF_PROVIDER_POOL=ninerouter
NINEROUTER_MODEL=oc/big-pickle
EOF

echo "==> Build e start (profile: $PROFILE)"
GIT_SHA="$(git rev-parse HEAD)"
docker compose --profile "$PROFILE" build --build-arg PKF_GIT_SHA="$GIT_SHA" pkf ninerouter
docker compose --profile "$PROFILE" up -d postgres pkf ninerouter --force-recreate
docker compose stop nginx 2>/dev/null || true

echo "==> Aguardando PKF ficar healthy..."
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8765/api/health | grep -q '"ok"'; then
    break
  fi
  sleep 2
done

echo "==> Auto-configurar OmniRoute/9Router (se 401 ou chave ausente)"
if curl -sf http://127.0.0.1:8765/api/health 2>/dev/null | grep -q '"ninerouter_ok": true'; then
  echo "OmniRoute OK"
else
  echo "OmniRoute com problema — executando fix-ninerouter-key.sh..."
  bash deploy/hostinger/fix-ninerouter-key.sh || echo "AVISO: configure NINEROUTER_KEY manualmente (dashboard OmniRoute)"
fi

echo "==> Status"
docker compose --profile "$PROFILE" ps
echo ""
curl -s http://127.0.0.1:8765/api/health || true
echo ""
echo "PKF: http://SEU_IP:8765/?token=SEU_PKF_AUTH_TOKEN"
echo "OmniRoute dashboard: ssh -L 20128:127.0.0.1:20128 root@VPS  →  http://localhost:20128"
