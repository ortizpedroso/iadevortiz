#!/usr/bin/env bash
# Recuperação emergencial após deploy de segurança (502 / PKF não sobe).
# Rode na VPS: cd /opt/pkf && bash deploy/hostinger/recover-production.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pkf}"
PROFILE="${PROFILE:-router}"
cd "$APP_DIR"

echo "==> Diagnóstico rápido"
docker compose --profile "$PROFILE" ps 2>/dev/null || true
echo ""

echo "==> Reparar .env (Postgres legacy + DATABASE_URL)"
bash deploy/hostinger/set-env-keys.sh

if docker volume ls 2>/dev/null | grep -Eq 'pkf-postgres|pkf_pkf-postgres'; then
  if ! grep -q '^POSTGRES_PASSWORD=pkf' .env 2>/dev/null; then
    echo "==> Forçando POSTGRES_PASSWORD=pkf (volume existente)"
    if grep -q '^POSTGRES_PASSWORD=' .env; then
      sed -i 's/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=pkf/' .env
    else
      echo 'POSTGRES_PASSWORD=pkf' >> .env
    fi
    if grep -q '^DATABASE_URL=' .env; then
      sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://pkf:pkf@postgres:5432/pkf|' .env
    else
      echo 'DATABASE_URL=postgresql+asyncpg://pkf:pkf@postgres:5432/pkf' >> .env
    fi
  fi
fi

echo "==> Subir Postgres + OmniRoute + PKF"
docker compose --profile "$PROFILE" up -d postgres ninerouter pkf --force-recreate

echo "==> Aguardando health (até 90s)"
for _ in $(seq 1 45); do
  if curl -sf http://127.0.0.1:8765/api/health 2>/dev/null | grep -q '"ok"'; then
    echo "OK: PKF respondendo"
    curl -s http://127.0.0.1:8765/api/health | python3 -m json.tool 2>/dev/null || true
    echo ""
    echo "==> Reconfigurar OmniRoute"
    ALLOW_LEGACY_OMNI_PASSWORD=1 bash deploy/hostinger/fix-ninerouter-key.sh || echo "AVISO: fix-ninerouter-key falhou"
    docker compose --profile "$PROFILE" up -d pkf --force-recreate
    PKF_HOST_DOMAIN="$(grep '^PKF_HOST_DOMAIN=' .env 2>/dev/null | head -n1 | cut -d= -f2- || true)"
    if [[ -n "$PKF_HOST_DOMAIN" ]]; then
      export PKF_HOST_DOMAIN
      bash deploy/hook-eventosbr-caddy.sh || echo "AVISO: hook Caddy falhou"
    fi
    exit 0
  fi
  sleep 2
done

echo "FALHOU — logs PKF:"
docker compose --profile "$PROFILE" logs pkf --tail 50 2>/dev/null || true
echo ""
echo "FALHOU — logs Postgres:"
docker compose --profile "$PROFILE" logs postgres --tail 20 2>/dev/null || true
exit 1
