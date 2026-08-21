#!/usr/bin/env bash
# Gera PKF_AUTH_TOKEN forte e recria o container (emergência pós-deploy).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
cd "$APP_DIR"

bash deploy/hostinger/set-env-keys.sh
docker compose --profile "${PROFILE:-router}" up -d pkf --force-recreate

echo "==> Aguardando health..."
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8765/api/health 2>/dev/null | grep -q '"ok"'; then
    echo "OK: PKF respondendo"
    echo "Token (guarde em local seguro):"
    grep '^PKF_AUTH_TOKEN=' .env | tail -n1
    exit 0
  fi
  sleep 2
done

echo "Falhou — logs:"
docker compose --profile "${PROFILE:-router}" logs pkf --tail 30
exit 1
